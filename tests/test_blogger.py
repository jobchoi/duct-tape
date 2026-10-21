"""Offline tests only: no Google account, API request or publication."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.blogger import cli

class Response:
    def __init__(self,data,status=200):self.data=data;self.status_code=status
    def json(self):return self.data

class Client:
    def __init__(self,responses):self.responses=list(responses);self.calls=[]
    def request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs))
        value=self.responses.pop(0)
        if isinstance(value,Exception):raise value
        return value

BLOG=Response({'id':'123','url':cli.BLOG})

class BloggerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'repo';self.folder=self.root/'docs/blog/blogger';self.folder.mkdir(parents=True)
        self.file=self.folder/'draft.md';self.file.write_text('# Test title\n\n작업 내용 **확인**\n')
        self.home=self.base/'config'
        self.patch=patch.object(cli,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)

    def test_markdown_preview_is_sanitized_and_unicode_preserved(self):
        self.file.write_text('# Test\n\n한글 **확인**\n<script>bad()</script><img src="https://example.com/tracker"><a href="javascript:bad()">link</a>')
        result=cli.render(self.file)
        self.assertIn('한글',result['content']);self.assertIn('<strong>확인</strong>',result['content'])
        self.assertNotIn('<script',result['content']);self.assertNotIn('<img',result['content']);self.assertNotIn('javascript:',result['content'])
        self.assertEqual(result['sha256'],cli.render(self.file)['sha256'])

    def test_source_must_be_in_blog_drafts_and_have_title(self):
        outside=self.base/'secret.md';outside.write_text('# Secret')
        with self.assertRaises(cli.BlogError):cli.render(outside)
        self.file.write_text('missing title')
        with self.assertRaises(cli.BlogError):cli.render(self.file)
        self.file.unlink();self.file.symlink_to(outside)
        with self.assertRaises(cli.BlogError):cli.render(self.file)

    def test_private_files_permissions_and_invalid_json(self):
        cli.private_write(self.home/'token.json','{"token":"TEST-ONLY"}')
        self.assertEqual(cli.private_read(self.home/'token.json')['token'],'TEST-ONLY')
        self.assertEqual((self.home/'token.json').stat().st_mode & 0o777,0o600)
        (self.home/'token.json').chmod(0o644)
        with self.assertRaises(cli.BlogError):cli.private_read(self.home/'token.json')
        (self.home/'token.json').chmod(0o600);(self.home/'token.json').write_text('{invalid')
        with self.assertRaises(cli.BlogError):cli.private_read(self.home/'token.json')

    def test_upload_is_draft_only_and_deduplicated(self):
        draft=cli.render(self.file);client=Client([BLOG,Response({'id':'456','status':'DRAFT'}),BLOG])
        with contextlib.redirect_stdout(io.StringIO()):
            cli.upload(client,self.home,draft);cli.upload(client,self.home,draft)
        posts=[c for c in client.calls if c[0]=='POST']
        self.assertEqual(len(posts),1);self.assertEqual(posts[0][2]['params'],{'isDraft':'true'})
        self.assertEqual(posts[0][2]['json']['content'],draft['content'])
        self.assertFalse(any('publish' in c[1] for c in client.calls))

    def test_definite_rejection_can_be_retried_after_fix(self):
        draft=cli.render(self.file)
        with self.assertRaises(cli.ApiError):cli.upload(Client([BLOG,Response({},403)]),self.home,draft)
        client=Client([BLOG,Response({'id':'456','status':'DRAFT'})])
        with contextlib.redirect_stdout(io.StringIO()):cli.upload(client,self.home,draft)
        self.assertEqual(len([c for c in client.calls if c[0]=='POST']),1)

    def test_unknown_outcome_blocks_repeat_and_can_reconcile(self):
        draft=cli.render(self.file);client=Client([BLOG,TimeoutError('TEST-ONLY')])
        with self.assertRaises(cli.BlogError):cli.upload(client,self.home,draft)
        retry=Client([BLOG])
        with self.assertRaises(cli.BlogError):cli.upload(retry,self.home,draft)
        self.assertFalse(any(c[0]=='POST' for c in retry.calls))
        marker='duct-draft-'+draft['sha256'][:24]
        reconcile=Client([BLOG,Response({'items':[{'id':'456','status':'DRAFT','labels':[marker]}]})])
        with contextlib.redirect_stdout(io.StringIO()):cli.reconcile(reconcile,self.home,draft)
        with contextlib.redirect_stdout(io.StringIO()):cli.upload(Client([BLOG]),self.home,draft)

    def test_changed_source_is_not_automatically_reuploaded(self):
        draft=cli.render(self.file)
        with contextlib.redirect_stdout(io.StringIO()):cli.upload(Client([BLOG,Response({'id':'456','status':'DRAFT'})]),self.home,draft)
        self.file.write_text('# Changed\n\nDifferent content')
        with self.assertRaises(cli.BlogError):cli.upload(Client([BLOG]),self.home,cli.render(self.file))

    def test_check_access_rejects_wrong_account(self):
        cli.check_access(Client([Response({'items':[{'id':'123'}]})]),'123')
        with self.assertRaises(cli.BlogError):cli.check_access(Client([Response({'items':[]})]),'123')

    def test_wrong_blog_or_non_draft_response_not_success(self):
        with self.assertRaises(cli.BlogError):cli.blog(Client([Response({'id':'123','url':'https://other.example/'})]))
        with self.assertRaises(cli.BlogError):cli.upload(Client([BLOG,Response({'id':'456','status':'LIVE'})]),self.home,cli.render(self.file))

    def test_reconcile_pages_and_rejects_missing_or_live_post(self):
        draft=cli.render(self.file)
        with self.assertRaises(cli.BlogError):cli.upload(Client([BLOG,TimeoutError()]),self.home,draft)
        marker='duct-draft-'+draft['sha256'][:24]
        client=Client([BLOG,Response({'nextPageToken':'page2'}),Response({'items':[{'id':'456','status':'LIVE','labels':[marker]}]})])
        with self.assertRaises(cli.BlogError):cli.reconcile(client,self.home,draft)
        self.assertEqual(client.calls[-1][2]['params']['pageToken'],'page2')

    def test_cli_preview_needs_no_credentials_and_upload_needs_review(self):
        output=self.base/'preview.html'
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(cli.main(['preview',str(self.file),'--output',str(output)]),0)
        self.assertIn('작업 내용',output.read_text())
        with patch.object(cli,'session') as session,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['upload',str(self.file)]),1);session.assert_not_called()

    def test_desktop_auth_uses_pkce_loopback_and_private_token(self):
        config={'installed':{'client_id':'TEST-CLIENT','client_secret':'TEST-ONLY',
            'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token'}}
        cli.private_write(self.home/'client_secret.json',json.dumps(config))
        with patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_config') as factory,contextlib.redirect_stdout(io.StringIO()):
            credentials=factory.return_value.run_local_server.return_value
            credentials.refresh_token='TEST-OFFLINE'
            credentials.to_json.return_value='{"refresh_token":"TEST-OFFLINE"}'
            cli.authenticate(self.home,8765,False)
            self.assertTrue(factory.call_args.kwargs['autogenerate_code_verifier'])
            self.assertEqual(factory.return_value.run_local_server.call_args.kwargs['host'],'127.0.0.1')
            self.assertFalse(factory.return_value.run_local_server.call_args.kwargs['open_browser'])
        self.assertEqual(cli.private_read(self.home/'token.json')['refresh_token'],'TEST-OFFLINE')
        cli.private_write(self.home/'client_secret.json',json.dumps({'web':{}}))
        with self.assertRaises(cli.BlogError):cli.authenticate(self.home,8765,False)

    def test_http_error_does_not_echo_response_or_exception_secrets(self):
        for client in [Client([Response({'secret':'TEST-ONLY'},403)]),Client([RuntimeError('TEST-ONLY')])]:
            with self.assertRaises(cli.BlogError) as raised:cli.request(client,'GET','/blogs/byurl')
            self.assertNotIn('TEST-ONLY',str(raised.exception))

if __name__=='__main__':unittest.main()
