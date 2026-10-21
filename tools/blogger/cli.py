"""Local preview, desktop OAuth and Blogger draft upload. No publish operation."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
BLOG = 'https://lealnspire.blogspot.com/'
SCOPE = 'https://www.googleapis.com/auth/blogger'
API = 'https://www.googleapis.com/blogger/v3'

class BlogError(Exception):
    pass

class ApiError(BlogError):
    def __init__(self,status):
        self.status=status
        super().__init__('Google API request failed (HTTP '+str(status)+'). Check API enablement, account access and quota.')


def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise BlogError('Configuration directory cannot be a symbolic link.')
    if os.name != 'nt':
        path.chmod(0o700)


def private_read(path):
    if path.is_symlink() or not path.is_file():
        raise BlogError('Required local credential file is missing or is a symbolic link.')
    if os.name != 'nt' and path.stat().st_mode & 0o077:
        raise BlogError('Credential file permissions must be 600.')
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError):
        raise BlogError('Credential JSON cannot be read. Do not paste its contents into chat.') from None


def private_write(path, value):
    private_dir(path.parent)
    handle, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def render(source):
    import bleach
    import markdown
    source = source.resolve()
    allowed = (ROOT/'docs/blog/blogger').resolve()
    if source.suffix != '.md' or not source.is_relative_to(allowed) or not source.is_file():
        raise BlogError('Choose a Markdown draft inside docs/blog/blogger/.')
    text = source.read_text(encoding='utf-8-sig')
    if len(text.encode('utf-8')) > 512000:
        raise BlogError('Draft is too large.')
    first, _, body = text.partition('\n')
    if not first.startswith('# ') or not first[2:].strip():
        raise BlogError('Draft must begin with a level-one title.')
    title = first[2:].strip()
    if len(title) > 200:
        raise BlogError('Title is too long.')
    html = markdown.markdown(body, extensions=['fenced_code', 'tables'])
    html = bleach.clean(html, tags=['p','br','hr','h2','h3','h4','ul','ol','li','strong','em','blockquote',
                                  'pre','code','a','table','thead','tbody','tr','th','td'],
                        attributes={'a':['href','title']}, protocols=['http','https','mailto'], strip=True)
    digest = hashlib.sha256((title+'\n'+html).encode()).hexdigest()
    return {'source':str(source.relative_to(ROOT)), 'title':title, 'content':html, 'sha256':digest}


def authenticate(home, port, browser):
    from google_auth_oauthlib.flow import InstalledAppFlow
    config = private_read(home/'client_secret.json')
    installed = config.get('installed')
    if not isinstance(installed, dict):
        raise BlogError('Use a desktop OAuth client JSON, not a web client.')
    if (installed.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth'
            or installed.get('token_uri') != 'https://oauth2.googleapis.com/token'):
        raise BlogError('Unexpected Google OAuth endpoints in client configuration.')
    flow = InstalledAppFlow.from_client_config(config, [SCOPE], autogenerate_code_verifier=True)
    try:
        credentials = flow.run_local_server(host='127.0.0.1', port=port, open_browser=browser,
            timeout_seconds=600, authorization_prompt_message='Open this Google consent URL in your browser:\n{url}',
            success_message='Blogger authorization received. You may close this tab.', prompt='consent')
    except Exception:
        raise BlogError('Google authorization did not finish. Check the browser and local callback; retry auth.') from None
    if not credentials.refresh_token:
        raise BlogError('Google did not provide an offline token. Reconnect with consent.')
    private_write(home/'token.json', credentials.to_json())
    print('Google account connected. Token stored locally; no post uploaded.')


def session(home):
    from google.auth.transport.requests import AuthorizedSession, Request
    from google.oauth2.credentials import Credentials
    data = private_read(home/'token.json')
    if data.get('token_uri') != 'https://oauth2.googleapis.com/token':
        raise BlogError('Unexpected token endpoint.')
    credentials = Credentials.from_authorized_user_info(data, [SCOPE])
    if not credentials.valid:
        try:
            credentials.refresh(Request())
        except Exception:
            raise BlogError('Account authorization expired or was revoked. Run auth again.') from None
        private_write(home/'token.json', credentials.to_json())
    return AuthorizedSession(credentials)


def request(client, method, path, **kwargs):
    try:
        response = client.request(method, API+path, timeout=30, allow_redirects=False, **kwargs)
    except Exception:
        raise BlogError('Google API response was not received. Upload outcome may be unknown; do not blindly retry.') from None
    if response.status_code >= 300:
        raise ApiError(response.status_code)
    try:
        return response.json()
    except ValueError:
        raise BlogError('Google API response could not be decoded.') from None


def blog(client):
    result = request(client, 'GET', '/blogs/byurl', params={'url':BLOG})
    if urlparse(result.get('url','')).hostname != urlparse(BLOG).hostname or not str(result.get('id','')).isdigit():
        raise BlogError('Target blog does not match the configured URL.')
    return str(result['id'])


def check_access(client, bid):
    result=request(client,'GET','/users/self/blogs',params={'view':'AUTHOR'})
    if not any(str(item.get('id',''))==bid for item in result.get('items',[])):
        raise BlogError('This Google account does not list the target blog as author/admin. Run auth with the correct account.')


def ledger(home):
    private_dir(home)
    db = sqlite3.connect(home/'uploads.sqlite3', timeout=10)
    if os.name != 'nt':
        (home/'uploads.sqlite3').chmod(0o600)
    db.execute('CREATE TABLE IF NOT EXISTS uploads (blog TEXT, source TEXT, digest TEXT, state TEXT, post TEXT, PRIMARY KEY(blog,source))')
    db.commit()
    return db


def upload(client, home, draft):
    bid = blog(client)
    with closing(ledger(home)) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT digest,state,post FROM uploads WHERE blog=? AND source=?',(bid,draft['source'])).fetchone()
        if existing:
            db.rollback()
            if existing[0] == draft['sha256'] and existing[1] == 'draft':
                print('Already uploaded as draft. Post ID: '+existing[2]);return
            raise BlogError('This source has a previous/uncertain upload or changed content. Run reconcile; do not create a duplicate.')
        db.execute('INSERT INTO uploads VALUES (?,?,?,?,?)',(bid,draft['source'],draft['sha256'],'pending',''))
        db.commit()
        # Persist before POST: unknown outcomes must be reconciled, never automatically retried.
        marker = 'duct-draft-'+draft['sha256'][:24]
        try:
            post = request(client,'POST','/blogs/'+bid+'/posts',params={'isDraft':'true'},
                           json={'kind':'blogger#post','title':draft['title'],'content':draft['content'],'labels':['DuctTape',marker]})
        except ApiError as error:
            if error.status in (400,401,403,404,405,413,422,429):
                # Google explicitly rejected this request; retry only on a later user command.
                db.execute('DELETE FROM uploads WHERE blog=? AND source=?',(bid,draft['source']))
                db.commit()
            raise
        if post.get('status') != 'DRAFT' or not str(post.get('id','')).isdigit():
            raise BlogError('Draft state not confirmed. Inspect Blogger and run reconcile.')
        db.execute('UPDATE uploads SET state=?,post=? WHERE blog=? AND source=?',('draft',str(post['id']),bid,draft['source']))
        db.commit()
    print('Draft uploaded. Post ID: '+str(post['id']))
    print('Review in Blogger: https://www.blogger.com/blog/posts/'+bid)


def reconcile(client, home, draft):
    bid = blog(client)
    with closing(ledger(home)) as db:
        previous = db.execute('SELECT digest,state,post FROM uploads WHERE blog=? AND source=?',(bid,draft['source'])).fetchone()
        if not previous:
            raise BlogError('No local upload record exists for this source.')
        if previous[0] != draft['sha256']:
            raise BlogError('Restore the uploaded version before reconciliation. Source changed.')
        marker = 'duct-draft-'+draft['sha256'][:24]
        posts=[];page=None
        while True:
            params={'status':['draft','live','scheduled'],'view':'AUTHOR','maxResults':100}
            if page:params['pageToken']=page
            result=request(client,'GET','/blogs/'+bid+'/posts',params=params)
            posts.extend(p for p in result.get('items',[]) if marker in p.get('labels',[]))
            page=result.get('nextPageToken')
            if not page:break
        if len(posts)!=1:
            raise BlogError('Expected exactly one matching remote post. Inspect Blogger manually; no new upload was made.')
        post=posts[0]
        if post.get('status')!='DRAFT':
            raise BlogError('Matching post is not a draft. No content was changed.')
        db.execute('UPDATE uploads SET state=?,post=? WHERE blog=? AND source=?',('draft',str(post['id']),bid,draft['source']))
        db.commit()
    print('Existing draft reconciled. Post ID: '+str(post['id']))


def main(argv=None):
    parser=argparse.ArgumentParser(description='Blogger drafts only; never publishes.')
    parser.add_argument('--config-dir',type=Path,default=Path.home()/'.config/duct-tape-blog')
    sub=parser.add_subparsers(dest='command',required=True)
    auth=sub.add_parser('auth');auth.add_argument('--port',type=int,default=8765);auth.add_argument('--no-browser',action='store_true')
    sub.add_parser('check')
    preview=sub.add_parser('preview');preview.add_argument('source',type=Path);preview.add_argument('--output',type=Path,default=ROOT/'downloads/blog-preview.html')
    for name in ('upload','reconcile'):
        command=sub.add_parser(name);command.add_argument('source',type=Path)
        if name=='upload':command.add_argument('--reviewed',action='store_true',help='Confirm this source version was reviewed.')
    args=parser.parse_args(argv)
    try:
        if args.command=='preview':
            import html
            draft=render(args.source);args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(draft['title'])+'</title><h1>'+html.escape(draft['title'])+'</h1>'+draft['content']+'</html>',encoding='utf-8')
            print('Preview saved: '+str(args.output));print('Draft SHA-256: '+draft['sha256']);return 0
        home=args.config_dir.expanduser().resolve()
        if home.is_relative_to(ROOT):
            raise BlogError('Store credentials outside the Git repository.')
        if args.command=='auth':
            authenticate(home,args.port,not args.no_browser);return 0
        if args.command=='upload' and not args.reviewed:
            raise BlogError('Preview and review the draft, then supply --reviewed.')
        draft=render(args.source) if args.command in ('upload','reconcile') else None
        with session(home) as client:
            if args.command=='check':
                bid=blog(client);check_access(client,bid)
                print('Connected author/admin target: '+BLOG+' (blog ID '+bid+')')
            elif args.command=='upload':upload(client,home,draft)
            else:reconcile(client,home,draft)
        return 0
    except BlogError as error:
        print(str(error),file=sys.stderr);return 1
    except Exception:
        print('Local operation failed. Check dependencies, file permissions and configuration. Secret values are omitted.',file=sys.stderr);return 1

if __name__=='__main__':
    raise SystemExit(main())
