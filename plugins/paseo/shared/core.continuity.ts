export const itemKey = (row:any) => `${row.kind ?? "goal"}:${row.id}`;
export function reconcile(previous:any[], incoming:any[]) {
  const old=new Map(previous.map(row=>[itemKey(row),row]));
  return incoming.map(row=>{const found=old.get(itemKey(row));return found && JSON.stringify(found)===JSON.stringify(row)?found:row;});
}
/** Rebuild the already loaded window, with one retry if a concurrent write invalidates a cursor. */
export async function readWindow(load:(payload:any)=>Promise<any>, payload:any, field:string, count:number) {
  for(let attempt=0;attempt<2;attempt++){
    const rows:any[]=[];let cursor:string|null=null,sequence:number|undefined;
    try {
      do {
        const page=await load({...payload,limit:Math.min(100,Math.max(1,count-rows.length)),...(cursor?{cursor}:{})});
        if(page.status!=="ok") throw Object.assign(Error(page.error??"목록 갱신 실패"),{code:page.code});
        if(sequence!==undefined && sequence!==page.sequence) throw Object.assign(Error("목록 변경"),{code:"STALE"});
        sequence=page.sequence;rows.push(...page.data[field]);cursor=page.data.next_cursor;
      }while(cursor && rows.length<count);
      return {items:rows,cursor,sequence};
    }catch(e){if((e as any).code!=="STALE"||attempt===1)throw e;}
  }
  throw Error("목록 갱신 실패");
}
