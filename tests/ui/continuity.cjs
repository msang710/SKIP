const modules=process.env.SKIP_UI_TEST_MODULES;
if(!modules)throw Error('Set SKIP_UI_TEST_MODULES to a directory containing esbuild, React, React Native Web and Playwright.');
const {build}=require(modules+'/esbuild');
const {chromium}=require(modules+'/@playwright/test');
const fs=require('fs'); const path=require('path');
(async()=>{
const root=process.cwd();fs.mkdirSync('.build',{recursive:true});
const mock=`export const useRpc=contract=>async(input={})=>{
 const state=window.fixture??(window.fixture={seq:1,session:0,expire:false,title:'설계 0',goals:[{id:'g',kind:'goal',revision:1,lifecycle:'active',fields:{title:'현재 목표',intent:'목적',success_definition:'완료'}}]});
 const ok=data=>({status:'ok',sequence:state.seq,data});
 if(contract.name==='skip.core.connect'){state.session++;return {sessionId:'s'+state.session,projectId:'p',canStart:false,target:'현재'};}
 if(contract.name==='skip.core.close')return {closed:true};
 if(state.expire){state.expire=false;return {status:'error',code:'CONTEXT_EXPIRED'};}
 const {query,payload={}}=input,start=Number(payload.cursor??0),limit=payload.limit??30;
 if(query==='changes')return ok({sequence:state.seq,events:[],complete:true});
 if(query==='status')return ok({goals:state.goals,facts:[],checks:[],remaining:[],work_items:[],next_cursor:null});
 if(query==='settings')return ok({settings:[]});
 if(query==='risks')return ok({assessments:[]});
 if(query==='record.list'){const rows=Array.from({length:120},(_,i)=>({kind:'plan',id:'d'+i,revision:i===0?state.seq:1,title:i===0?state.title:'설계 '+i}));return ok({items:rows.slice(start,start+limit),next_cursor:start+limit<120?String(start+limit):null});}
 if(query==='record')return ok({kind:'plan',id:payload.id,revision:state.seq,current_revision:state.seq,fields:{title:state.title,design_body:'본문 '+state.seq},children:{}});
 return ok({items:[],next_cursor:null});
};`;
const result=await build({stdin:{contents:`import React from 'react'; import {createRoot} from 'react-dom/client';import {CorePanel} from '${root}/plugins/paseo/core.panel.client.tsx';createRoot(document.getElementById('root')).render(<CorePanel context="workspace" workspaceId="test" host={{id:'local'}} layout={{compact:false,platform:'web'}} theme={{colors:{foreground:'#eaeaea',foregroundMuted:'#a7a7b0',surface0:'#17171c',accent:'#a9baff'}}}/>);`,resolveDir:root,loader:'tsx'},bundle:true,write:false,define:{global:'globalThis'},jsx:'automatic',alias:{'react':modules+'/react','react-dom':modules+'/react-dom','react-native':modules+'/react-native-web'},plugins:[{name:'mock-host',setup(b){b.onResolve({filter:/^@getpaseo\/plugin$/},()=>({path:'host',namespace:'mock'}));b.onLoad({filter:/.*/,namespace:'mock'},()=>({contents:mock,loader:'js'}));b.onResolve({filter:/core.shared$/},()=>({path:'contracts',namespace:'contracts'}));b.onLoad({filter:/.*/,namespace:'contracts'},()=>({contents:`export const connectCore={name:'skip.core.connect'},queryCore={name:'query'},userCore={name:'user'},closeCore={name:'skip.core.close'};` }));}}]});
const browser=await chromium.launch({headless:true,...(process.env.SKIP_UI_TEST_BROWSER?{executablePath:process.env.SKIP_UI_TEST_BROWSER}:{})});
try{
const page=await browser.newPage({viewport:{width:1200,height:800}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.setContent('<style>html,body,#root{height:100%;margin:0}#root{display:flex}#root>div{flex:1}</style><div id="root"></div>');await page.addScriptTag({content:result.outputFiles[0].text});

await page.getByRole('button',{name:'설정',exact:true}).click();
await page.getByRole('button',{name:'+ 규칙 추가',exact:true}).click();
await page.getByLabel('사용자 규칙 내용').fill('연결이 복구돼도 이 초안을 유지');
await page.getByRole('button',{name:'설계',exact:true}).click();
await page.getByRole('button',{name:'기록 더 보기',exact:true}).click();
if(await page.getByRole('button',{name:/^설계 [0-9]+ plan$/}).count()<60) {
 const count=await page.getByRole('button',{name:/설계 [0-9]+/}).count();if(count<60)throw Error('Page was not expanded: '+count);
}
await page.evaluate(()=>{window.fixture.seq++;window.fixture.title='수정된 설계';window.fixture.goals.unshift({id:'new',kind:'goal',revision:1,lifecycle:'active',fields:{title:'새 목표',intent:'목적',success_definition:'완료'}});window.fixture.expire=true;});
await page.getByRole('button',{name:/수정된 설계/}).waitFor({timeout:15000});
await page.getByRole('button',{name:'새 목표',exact:true}).waitFor();
if(await page.getByRole('button',{name:/설계 59/}).count()!==1)throw Error('Loaded window lost after refresh');
await page.getByRole('button',{name:'설정',exact:true}).click();
await page.screenshot({path:'.build/continuity-debug.png'});
if(await page.getByLabel('사용자 규칙 내용').inputValue({timeout:3000})!=='연결이 복구돼도 이 초안을 유지')throw Error('Settings draft lost');
await page.getByRole('button',{name:'설계',exact:true}).click();
await page.getByRole('button',{name:/수정된 설계/}).click();
await page.evaluate(()=>{window.fixture.seq++;window.fixture.title='다시 바뀐 설계';});
await page.getByRole('button',{name:'변경된 내용 보기',exact:true}).waitFor({timeout:15000});
if(await page.getByText('본문 2',{exact:true}).count()!==1)throw Error('Reading text was replaced');
await page.getByRole('button',{name:'변경된 내용 보기',exact:true}).click();
await page.getByText('본문 3',{exact:true}).waitFor();
await page.screenshot({path:'.build/continuity-wide.png'});
await page.setViewportSize({width:390,height:844});
await page.screenshot({path:'.build/continuity-narrow.png'});
if(errors.length)throw Error(errors.join('\n'));
console.log(JSON.stringify({passed:true,checks:['external updates','loaded window retained','reconnection','draft retained','reading revision retained','wide and narrow rendering'],session:await page.evaluate(()=>window.fixture.session)}));
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
