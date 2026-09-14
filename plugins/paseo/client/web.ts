import {Platform} from "react-native";
// This is the sole browser boundary. Native clients retain the selectable caller fallback.
type BrowserStorage={getItem(key:string):string|null;setItem(key:string,value:string):void};
type Browser={localStorage?:BrowserStorage;navigator?:{clipboard?:{writeText(text:string):Promise<void>}};addEventListener?:(type:string,listener:(event:any)=>void)=>void;removeEventListener?:(type:string,listener:(event:any)=>void)=>void};
const browser=()=>Platform.OS==="web"?globalThis as unknown as Browser:undefined;
export function deviceStorage():BrowserStorage|undefined{try{return browser()?.localStorage;}catch{return undefined;}}
export function subscribeStorage(key:string,listener:(value:string|null)=>void){
 const host=browser();const handler=(event:any)=>{if((event.key===key||event.key===null)&&event.storageArea===deviceStorage())listener(event.newValue);};
 host?.addEventListener?.("storage",handler);return()=>host?.removeEventListener?.("storage",handler);
}
export async function copyText(text:string){const clipboard=browser()?.navigator?.clipboard;if(!clipboard)throw Error("Clipboard unavailable");await clipboard.writeText(text);}
