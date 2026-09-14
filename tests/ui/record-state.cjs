const modules=process.env.SKIP_UI_TEST_MODULES;
if(!modules)throw Error('Set SKIP_UI_TEST_MODULES');
const {build}=require(modules+'/esbuild');const {chromium}=require(modules+'/@playwright/test');
(async()=>{
const contents=`import React from 'react';import {createRoot} from 'react-dom/client';import {RecordStateMenu} from '${process.cwd()}/plugins/paseo/client/core.record-state';
const root=createRoot(document.getElementById('root'));
window.record={kind:'plan',id:'a',revision:1,current_revision:1,state_version:2,lifecycle:'active',goal_id:'g'};window.fixtureHistory=[];window.calls=[];
window.render=()=>root.render(<RecordStateMenu record={structuredClone(window.record)} theme={{colors:{foreground:'#eee',foregroundMuted:'#aaa',surface0:'#222',accent:'#aaf'}}} disabled={false}
 load={async(q,p)=>q==='record.list'?{data:{items:[{kind:'plan',id:'b',revision:3,title:'새 설계',lifecycle:'active'}],next_cursor:null}}:{data:{items:window.fixtureHistory,next_cursor:null}}}
 open={async r=>{window.opened=r;}}
 change={async p=>{if(p.state_version!==window.record.state_version)throw Error('기록이 변경되었습니다.');const previous={lifecycle:window.record.lifecycle,reason:window.record.state_change?.reason??'',replacement:window.record.state_change?.replacement??null};window.calls.push(p);const sc={id:String(window.calls.length),from_state:p.from_state,to_state:p.to_state,reason:p.reason??'',replacement:p.replacement??null,created_at:'오늘'};window.record={...window.record,lifecycle:p.to_state,state_version:p.state_version+1,state_change:sc};window.fixtureHistory.unshift(sc);window.render();return {...window.record,previous};}}/>);window.render();`;
const bundle=await build({stdin:{contents,resolveDir:process.cwd(),loader:'tsx'},bundle:true,write:false,define:{global:'globalThis'},jsx:'automatic',alias:{react:modules+'/react','react-dom':modules+'/react-dom','react-native':modules+'/react-native-web'}});
const browser=await chromium.launch({headless:true,...(process.env.SKIP_UI_TEST_BROWSER?{executablePath:process.env.SKIP_UI_TEST_BROWSER}:{})});
try{const page=await browser.newPage({viewport:{width:800,height:800}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.setContent('<style>body{background:#222;margin:0;padding:12px}</style><div id="root"></div>');await page.addScriptTag({content:bundle.outputFiles[0].text});
const click=name=>page.getByRole('button',{name,exact:true}).click();
await click('문서 상태 변경');await click('반려');
if(await page.getByRole('button',{name:'상태 저장',exact:true}).isEnabled())throw Error('Reason not required');
await page.getByRole('textbox',{name:'반려 이유',exact:true}).fill('요구사항을 충족하지 않음');await click('상태 저장');await page.getByText('반려로 변경했습니다.',{exact:true}).waitFor();
await click('문서 상태 되돌리기');await page.waitForFunction(()=>window.record.lifecycle==='active');
await click('문서 상태 변경');await click('다른 문서로 대체');await page.getByRole('textbox',{name:'대체 이유',exact:true}).fill('새 설계가 동시성을 보장함');
if(await page.getByRole('button',{name:'상태 저장',exact:true}).isEnabled())throw Error('Replacement not required');
await page.getByRole('radio',{name:'새 설계',exact:true}).click();await click('상태 저장');await page.getByText('대체로 변경했습니다.',{exact:true}).waitFor();
await click('대체 문서 보기');if(await page.evaluate(()=>window.opened.id)!=='b')throw Error('Wrong replacement opened');
await click('문서 상태 변경');await click('변경 이력');await page.getByText('새 설계가 동시성을 보장함',{exact:true}).last().waitFor();
await page.evaluate(()=>{window.record.state_version++;window.render();});await click('문서 상태 되돌리기');await page.getByText('기록이 변경되었습니다.',{exact:true}).waitFor();
if(await page.evaluate(()=>window.record.lifecycle)!=='superseded')throw Error('Undo overwrote concurrent change');
await page.setViewportSize({width:390,height:844});await page.screenshot({path:'.build/record-state-narrow.png'});
if(errors.length)throw Error(errors.join('\n'));console.log('Record rejection, replacement, exact navigation, history and stale undo passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
