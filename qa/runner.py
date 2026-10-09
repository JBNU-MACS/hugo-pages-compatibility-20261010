"""Build the exact tracked files prepared and committed on macOS."""
from pathlib import Path
import argparse,concurrent.futures as cf,hashlib,html,json,os,shutil,subprocess,tarfile,time,urllib.request,urllib.parse
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parent.parent

def download(url,path,sha=None):
 for attempt in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Hugo-Compatibility-Audit'}),timeout=90) as r,path.open('wb') as f:shutil.copyfileobj(r,f)
   if sha and hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise RuntimeError('Checksum mismatch: '+path.name)
   return
  except Exception:
   if attempt==2:raise
   time.sleep(3)

def extract(archive,dest):
 dest.mkdir(parents=True,exist_ok=True)
 with tarfile.open(archive) as t:
  def bounded(member,path):
   # Original example symlinks outside the extracted repository are unused;
   # the prepared site contains regular materialized files.
   try:return tarfile.data_filter(member,path)
   except tarfile.FilterError:
    if member.issym() or member.islnk():return None
    raise
  t.extractall(dest,filter=bounded)

class Links(HTMLParser):
 def __init__(self):super().__init__();self.assets=set();self.links=set()
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag in ['img','script','source','video','audio']:
   for key in ['src','poster','data-src']:
    if d.get(key):self.assets.add(d[key])
  if tag=='link' and d.get('rel') in ['stylesheet','icon','apple-touch-icon','preload','modulepreload'] and d.get('href'):self.assets.add(d['href'])
  if tag=='a' and d.get('href'):self.links.add(d['href'])

def build(shard_id,base):
 manifest=json.loads((ROOT/'qa/manifest.json').read_text());shard=next(s for s in manifest['shards'] if s['id']==shard_id)
 work=Path(os.environ['RUNNER_TEMP'])/'theme-audit';work.mkdir(exist_ok=True)
 bundle=work/shard['archive'];download('https://github.com/'+manifest['repository']+'/releases/download/'+manifest['release_tag']+'/'+shard['archive'],bundle,shard['sha256']);extract(bundle,work/'archives');bundle.unlink()
 out=ROOT/'audit-output';(out/'site').mkdir(parents=True,exist_ok=True);reports=out/'reports';reports.mkdir(exist_ok=True)
 results=[]
 for row in shard['themes']:
  slug=row['slug'];start=time.time();logs=[];result={'slug':slug,'group':shard['group'],'shard':shard_id,'mac_git_tree':row['git_tree'],'source_archive_sha256':row['archive_sha256']}
  root=work/'projects'/slug
  try:
   archive=work/'archives'/(slug+'.tar.gz');assert hashlib.sha256(archive.read_bytes()).hexdigest()==row['archive_sha256'];extract(archive,root.parent);archive.unlink()
   helper=root/'.github/pages_build.py';assert hashlib.sha256(helper.read_bytes()).hexdigest()==manifest['script_sha256']
   state=json.loads((root/'.github-pages.json').read_text());version=state['version'];tools=work/'tools'/version
   if not (tools/'hugo').exists():
    z=work/('hugo-'+version+'.tgz');download(f'https://github.com/gohugoio/hugo/releases/download/v{version}/hugo_extended_{version}_linux-amd64.tar.gz',z);extract(z,tools);z.unlink()
   sitebase=base.rstrip('/')+'/'+slug+'/'
   env=dict(os.environ,HUGO_ENVIRONMENT='production',HUGO_CACHEDIR=str(work/'hugo-cache'),GOMAXPROCS='2',SITE_BASE_URL=sitebase,PATH=str(tools)+os.pathsep+os.environ['PATH'])
   for mode in ['--dependencies','--build']:
    result['phase']=mode
    with (reports/(slug+'.log')).open('a') as log:
     log.write(mode+'\n');log.flush();cp=subprocess.run(['python',str(helper),mode],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    if cp.returncode:raise RuntimeError(mode+' exit '+str(cp.returncode))
   public=root/'public';assert (public/'index.html').is_file()
   parser=Links();parser.feed((public/'index.html').read_text())
   def local_target(url):
    u=urllib.parse.urlsplit(urllib.parse.urljoin(sitebase,url));b=urllib.parse.urlsplit(sitebase)
    if u.netloc!=b.netloc or not u.path.startswith(b.path):return None
    path=public/urllib.parse.unquote(u.path[len(b.path):]);return path if path.is_file() else path/'index.html'
   assets=[];missing=[]
   for url in parser.assets:
    path=local_target(url)
    if path is None:continue
    (assets if path.is_file() else missing).append(urllib.parse.urljoin(sitebase,url))
   pages=[]
   for url in sorted(parser.links):
    path=local_target(url)
    if path is not None and path.is_file() and path.suffix=='.html':pages.append(urllib.parse.urljoin(sitebase,url))
    if len(pages)>=3:break
   result.update(status='passed',version=version,base_url=sitebase,homepage_assets=assets,homepage_missing_source_assets=missing,internal_pages=pages,html_files=sum(1 for _ in public.rglob('*.html')))
   shutil.move(str(public),str(out/'site'/slug))
  except Exception as e:result.update(status='failed',error=str(e))
  finally:
   result['seconds']=round(time.time()-start,2);results.append(result)
   (reports/f'shard-{shard_id:02}.json').write_text(json.dumps(results,indent=2));print(slug,result['status'],result.get('error',''),flush=True)
   if root.exists():shutil.rmtree(root)
 return 0 if all(x['status']=='passed' for x in results) else 1

def assemble(group):
 site=ROOT/'audit-output/site';reports=ROOT/'audit-output/reports';results=[]
 for p in reports.glob('shard-*.json'):results.extend(json.loads(p.read_text()))
 manifest=json.loads((ROOT/'qa/manifest.json').read_text());expected={r['slug'] for s in manifest['shards'] if s['group']==group for r in s['themes']}
 assert {r['slug'] for r in results}==expected
 assert all(r['status']=='passed' and (site/r['slug']/'index.html').is_file() for r in results)
 (site/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>Hugo 배포 검증</title><h1>Hugo 배포 검증 — 묶음 '+str(group+1)+'</h1><p>Mac에서 ZIP을 풀어 준비하고 Git에 커밋한 파일의 GitHub Actions 빌드 및 Pages 배포 결과입니다.</p><ul>'+''.join('<li><a href="'+html.escape(r['slug'])+'/">'+html.escape(r['slug'])+'</a></li>' for r in sorted(results,key=lambda r:r['slug']))+'</ul></html>')
 (site/'audit-deployment.json').write_text(json.dumps({'group':group,'run_id':os.environ.get('GITHUB_RUN_ID'),'themes':sorted(expected)}));(site/'.nojekyll').touch()
 (reports/'batch.json').write_text(json.dumps(results,indent=2));print('Ready to deploy',len(results),'themes')

def live(base,group):
 reports=ROOT/'audit-output/reports';results=json.loads((reports/'batch.json').read_text());site=ROOT/'audit-output/site'
 for attempt in range(12):
  try:
   with urllib.request.urlopen(base.rstrip('/')+'/audit-deployment.json?run='+os.environ.get('GITHUB_RUN_ID',''),timeout=30) as r:marker=json.load(r)
   if marker['group']==group and marker['run_id']==os.environ.get('GITHUB_RUN_ID'):break
  except Exception:pass
  time.sleep(10)
 else:raise RuntimeError('Deployed batch marker did not become available')
 checks=[]
 for row in results:
  checks.append((row['slug'],'homepage',row['base_url']))
  for url in row['homepage_assets']:checks.append((row['slug'],'asset',url))
  for url in row['internal_pages']:checks.append((row['slug'],'page',url))
 def check(item):
  slug,kind,url=item
  for attempt in range(3):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,method='HEAD' if kind=='asset' else 'GET'),timeout=35) as r:
     content=r.read() if kind!='asset' else b'';result=dict(slug=slug,kind=kind,url=url,status=r.status,content_type=r.headers.get('content-type'))
     if kind=='homepage':
      local=(site/slug/'index.html').read_bytes();result['matches_built_html']=hashlib.sha256(content).digest()==hashlib.sha256(local).digest()
     return result
   except Exception as e:
    if attempt==2:return dict(slug=slug,kind=kind,url=url,error=str(e))
    time.sleep(2)
 with cf.ThreadPoolExecutor(max_workers=8) as pool:checked=list(pool.map(check,checks))
 bad=[r for r in checked if r.get('status')!=200 or r.get('matches_built_html') is False]
 (reports/'live-checks.json').write_text(json.dumps({'group':group,'checks':checked,'failures':bad,'themes':len(results),'deployed_run_id':os.environ.get('GITHUB_RUN_ID')},indent=2));print('Live themes',len(results),'checks',len(checked),'failures',len(bad))
 return 1 if bad else 0

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['build','assemble','live']);p.add_argument('--shard',type=int);p.add_argument('--group',type=int);p.add_argument('--base',default=os.environ.get('SITE_BASE_URL',''));a=p.parse_args()
 raise SystemExit(build(a.shard,a.base) if a.mode=='build' else live(a.base,a.group) if a.mode=='live' else assemble(a.group))
