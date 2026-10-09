from pathlib import Path
import concurrent.futures as cf,subprocess,json,hashlib,shutil,time
R=Path('/tmp/hugo-e2e-20261010');OLD=Path('/tmp/hugo-all-themes-20261010');SCRIPT=Path('/Volumes/DriveS/Projects/tmp/hugo-profile-master/tmp/github-pages-python/prepare_github_pages.py');REPO='https://github.com/JBNU-MACS/hugo-pages-compatibility-20261010.git'
for name in ['mac-v31','logs','prepared-archives']:(R/name).mkdir(exist_ok=True)
rows=json.loads((OLD/'all-catalog.json').read_text())
def audit(row):
 slug=row['slug'];folder=R/'mac-v31'/slug;logs=[];phase='extract';start=time.time()
 def run(args,cwd=None,input=None,timeout=240):
  cp=subprocess.run(args,cwd=cwd,input=input,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
  logs.append('$ '+' '.join(map(str,args))+'\n'+cp.stdout)
  if cp.returncode:raise RuntimeError(f'{args[0]} returned {cp.returncode}: '+cp.stdout[-2200:])
  return cp.stdout
 try:
  archive=OLD/'archives'/(slug+'.zip');assert hashlib.sha256(archive.read_bytes()).hexdigest()==row['sha256']
  if folder.exists():shutil.rmtree(folder)
  folder.mkdir();run(['ditto','-x','-k',str(archive),str(folder)])
  roots=[x for x in folder.iterdir() if x.is_dir() and x.name!='__MACOSX'];assert len(roots)==1;root=roots[0]
  shutil.copy2(SCRIPT,root/SCRIPT.name);phase='prepare'
  run(['python3',SCRIPT.name],cwd=root,input=REPO+'\n')
  state=json.loads((root/'.github-pages.json').read_text());assert state['audited'] and state['slug']==slug
  phase='git'
  for args in [['init','-b','main'],['config','user.name','Hugo Compatibility Test'],['config','user.email','hugo-compatibility-test@users.noreply.github.com'],['remote','add','origin',REPO],['add','--all'],['commit','-m','Prepare '+slug+' from official Download ZIP']]:run(['git']+args,cwd=root)
  required=['.github/workflows/hugo-pages.yml','.github/pages_build.py','.github-pages.json','site/pages.json']
  for name in state['config'].split(','):required.append('site/'+name)
  run(['git','ls-files','--error-unmatch']+required,cwd=root)
  tree=run(['git','rev-parse','HEAD^{tree}'],cwd=root).strip();commit=run(['git','rev-parse','HEAD'],cwd=root).strip()
  out=R/'prepared-archives'/(slug+'.tar.gz');run(['git','archive','--format=tar.gz','--prefix='+slug+'/', '-o',str(out),'HEAD'],cwd=root)
  phase='repeat';marker=root/'site/student-test.txt';marker.write_text('Student edit\n')
  run(['python3',SCRIPT.name],cwd=root,input=REPO+'\n');assert marker.read_text()=='Student edit\n'
  return dict(slug=slug,status='passed',source_zip_sha256=row['sha256'],archive_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),archive_bytes=out.stat().st_size,version=state['version'],git_commit=commit,git_tree=tree,local_git=True,push_per_theme=False,root=str(root),seconds=round(time.time()-start,2))
 except Exception as er:return dict(slug=slug,status='failed',phase=phase,error=str(er),seconds=round(time.time()-start,2))
 finally:(R/'logs'/(slug+'-mac.log')).write_text('\n'.join(logs))
results=[]
with cf.ThreadPoolExecutor(max_workers=6) as ex:
 for f in cf.as_completed([ex.submit(audit,r) for r in rows]):
  r=f.result();results.append(r);(R/'mac-results.json').write_text(json.dumps(results,indent=2));print(len(results),r['slug'],r['status'],r.get('error',''),flush=True)
