const modules=process.env.SKIP_UI_TEST_MODULES;
if(!modules)throw Error('Set SKIP_UI_TEST_MODULES');
const {build}=require(modules+'/esbuild');const {chromium}=require(modules+'/@playwright/test');const fs=require('fs');
(async()=>{
const contents=`import React from 'react';import {createRoot} from 'react-dom/client';import {ProjectProfile} from '${process.cwd()}/plugins/paseo/client/core.profile';
const root=createRoot(document.getElementById('root'));window.state={metadata:{revision:null},profile:null,proposals:[]};window.seq=1;window.project='p';
window.render=()=>root.render(<ProjectProfile key={window.project} draftKey={window.project} theme={{colors:{foreground:'#eee',foregroundMuted:'#aaa',surface0:'#222',accent:'#aaf'}}} revision={window.seq} load={async()=>({data:window.state})} save={async(op,p)=>{window.calls=(window.calls??0)+1;if(p.expected_revision!==window.state.metadata.revision)throw Error('STALE');const revision=(p.expected_revision??0)+1;const value=op==='project.profile.accept'?window.state.proposals.find(v=>v.revision===p.revision):p;window.state={metadata:{revision},profile:{...value,revision},proposals:[]};}}/>);window.render();`;
const bundle=await build({stdin:{contents,resolveDir:process.cwd(),loader:'tsx'},bundle:true,write:false,define:{global:'globalThis'},jsx:'automatic',alias:{react:modules+'/react','react-dom':modules+'/react-dom','react-native':modules+'/react-native-web'}});
const browser=await chromium.launch({headless:true,...(process.env.SKIP_UI_TEST_BROWSER?{executablePath:process.env.SKIP_UI_TEST_BROWSER}:{})});
try{const page=await browser.newPage({viewport:{width:850,height:800}});await page.setContent('<html><body style="background:#222;padding:16px"><div id="root"></div></body></html>');await page.addScriptTag({content:bundle.outputFiles[0].text});
await page.getByRole('button',{name:'프로젝트 소개 작성',exact:true}).click();await page.getByLabel('프로젝트 한 줄 소개',{exact:true}).fill('업무를 위한 도구');await page.getByLabel('프로젝트 소개 본문',{exact:true}).fill('## 목적\n사용자가 결정하고 에이전트가 구현한다.');await page.getByRole('button',{name:'소개 저장',exact:true}).click();await page.getByRole('button',{name:'소개 편집',exact:true}).waitFor();
await page.getByRole('button',{name:'소개 편집',exact:true}).click();await page.getByLabel('프로젝트 소개 본문',{exact:true}).fill('내가 작성 중인 초안');
await page.evaluate(()=>{window.state={metadata:{revision:2},profile:{revision:2,tagline:'다른 세션의 수정',body_markdown:'최신 내용'},proposals:[]};window.seq++;window.render();});await page.getByRole('button',{name:'비교 완료 · 최신 버전에 적용',exact:true}).waitFor();
if(await page.getByLabel('프로젝트 소개 본문',{exact:true}).inputValue()!=='내가 작성 중인 초안')throw Error('Draft lost');
await page.evaluate(()=>{window.project='other';window.seq++;window.render();});await page.getByRole('button',{name:'소개 편집',exact:true}).waitFor();
await page.evaluate(()=>{window.project='p';window.seq++;window.render();});await page.getByLabel('프로젝트 소개 본문',{exact:true}).waitFor();if(await page.getByLabel('프로젝트 소개 본문',{exact:true}).inputValue()!=='내가 작성 중인 초안')throw Error('Draft navigation loss');
await page.getByRole('button',{name:'비교 완료 · 최신 버전에 적용',exact:true}).click();await page.getByRole('button',{name:'소개 저장',exact:true}).click();await page.getByRole('button',{name:'소개 편집',exact:true}).waitFor();
// Acceptance must retain the complete Markdown, including text after 500 characters.
await page.evaluate(()=>{const body='## 긴 소개\n\n'+'프로젝트 원칙을 설명합니다. '.repeat(60)+'\n\n**마지막 문단까지 보입니다.**';window.state.proposals=[{revision:window.state.metadata.revision+1,base_revision:window.state.metadata.revision,tagline:'긴 소개',body_markdown:body,content_digest:'proposal'}];window.seq++;window.render();});
await page.getByRole('button',{name:'소개 접기',exact:true}).click();
await page.getByRole('button',{name:'변경안 적용',exact:true}).click();
await page.getByRole('button',{name:'소개 접기',exact:true}).waitFor();
await page.getByText('마지막 문단까지 보입니다.',{exact:true}).waitFor();
await page.getByRole('button',{name:'소개 접기',exact:true}).click();
if(await page.getByText('마지막 문단까지 보입니다.',{exact:true}).count())throw Error('Collapsed profile body remained');
await page.getByRole('button',{name:'소개 펼치기',exact:true}).click();
await page.getByText('마지막 문단까지 보입니다.',{exact:true}).waitFor();
fs.mkdirSync('.build',{recursive:true});await page.screenshot({path:'.build/profile-wide.png'});await page.setViewportSize({width:390,height:800});await page.screenshot({path:'.build/profile-narrow.png'});console.log('Profile edit, remote conflict, project isolation, draft restoration, full accepted Markdown and collapse passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
