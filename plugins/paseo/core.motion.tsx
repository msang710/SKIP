import React,{createContext,useContext,useEffect,useRef,useState} from "react";
import {AccessibilityInfo,Animated,LayoutAnimation,Platform,ScrollView} from "react-native";
import {itemKey} from "./core.continuity";
import {tint} from "./core.visual";

const Anchors=createContext<((key:string,y:number,height:number)=>void)|null>(null);
export function ContinuityScroll({scene,memory,children,...props}:any){
 const view=useRef<ScrollView>(null),positions=useRef(new Map<string,{y:number;height:number}>());
 const anchor=useRef<{key:string;offset:number}|null>(null),restored=useRef(false);
 const lastScene=useRef(scene);
 if(lastScene.current!==scene){lastScene.current=scene;restored.current=false;positions.current.clear();anchor.current=null;}
 const register=(key:string,y:number,height:number)=>{
  if(height<0){positions.current.delete(key);if(anchor.current?.key===key)anchor.current=null;return;}
  positions.current.set(key,{y,height});
  if(anchor.current?.key===key){
   const next=Math.max(0,y+anchor.current.offset);
   if(Math.abs(next-(memory.current[scene]??0))>1){memory.current[scene]=next;view.current?.scrollTo({y:next,animated:false});}
  }
 };

 return <Anchors.Provider value={register}><ScrollView {...props} key={scene} ref={view}
  onContentSizeChange={()=>{if(!restored.current){restored.current=true;view.current?.scrollTo({y:memory.current[scene]??0,animated:false});}}}
  scrollEventThrottle={32}
  onScroll={event=>{
   if(!restored.current)return;
   const y=event.nativeEvent.contentOffset.y;memory.current[scene]=y;
   const visible=[...positions.current].filter(([,p])=>p.y<=y&&p.y+p.height>y).sort((a,b)=>b[1].y-a[1].y)[0];
   anchor.current=visible?{key:visible[0],offset:y-visible[1].y}:null;
  }}>{children}</ScrollView></Anchors.Provider>;
}

/** Stable row identities keep input/selection mounted. Only real updates animate. */
export function ChangeList({rows,render,theme}:{rows:any[];render:(row:any,index:number)=>React.ReactNode;theme:any}) {
 const [shown,setShown]=useState(rows),[removed,setRemoved]=useState(new Set<string>());
 const [added,setAdded]=useState(new Set<string>());
 const reduce=useRef(true),previous=useRef(rows),timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 useEffect(()=>{let alive=true;void AccessibilityInfo.isReduceMotionEnabled().then(v=>{if(alive)reduce.current=v;});
  const subscription=AccessibilityInfo.addEventListener("reduceMotionChanged",v=>{reduce.current=v;});
  return()=>{alive=false;subscription.remove();if(timer.current)clearTimeout(timer.current);};
 },[]);
 useEffect(()=>{
  if(previous.current===rows)return;
  if(timer.current)clearTimeout(timer.current);
  const old=previous.current;previous.current=rows;
  const keys=new Set(rows.map(itemKey)),oldKeys=new Set(old.map(itemKey));
  // An initially empty/loading list is not a stream of newly created records.
  const fresh=new Set(old.length?rows.filter(r=>!oldKeys.has(itemKey(r))).map(itemKey):[]);
  const gone=old.filter(r=>!keys.has(itemKey(r)));
  setAdded(fresh);
  if(!reduce.current&&Platform.OS!=="web")LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
  if(gone.length&&!reduce.current){
   const merged=[...rows];for(const row of gone)merged.splice(Math.min(old.indexOf(row),merged.length),0,row);
   setRemoved(new Set(gone.map(itemKey)));setShown(merged);
   timer.current=setTimeout(()=>{if(Platform.OS!=="web")LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);setRemoved(new Set());setShown(rows);},160);
  }else{setRemoved(new Set());setShown(rows);}
 },[rows]);
 return <>{shown.map((row,index)=><MotionRow key={itemKey(row)} row={row} entering={added.has(itemKey(row))} leaving={removed.has(itemKey(row))} reduce={reduce} theme={theme}>{render(row,index)}</MotionRow>)}</>;
}
function MotionRow({row,entering,leaving,reduce,theme,children}:any){
 const register=useContext(Anchors),lastY=useRef<number|null>(null);
 const registrar=useRef(register);registrar.current=register;
 useEffect(()=>()=>{registrar.current?.(itemKey(row),0,-1);},[]);
 const offset=useRef(new Animated.Value(0)).current;
 const opacity=useRef(new Animated.Value(entering?0:1)).current;
 const highlight=useRef(new Animated.Value(0)).current;
 const previous=useRef(row);
 useEffect(()=>{
  if(reduce.current){opacity.setValue(leaving?0:1);return;}
  const animation=Animated.timing(opacity,{toValue:leaving?0:1,duration:160,useNativeDriver:false});animation.start();return()=>animation.stop();
 },[entering,leaving]);
 useEffect(()=>{
  if(previous.current===row)return;previous.current=row;
  if(reduce.current)return;
  highlight.setValue(1);const animation=Animated.timing(highlight,{toValue:0,duration:650,useNativeDriver:false});animation.start();return()=>animation.stop();
 },[row]);
 return <Animated.View onLayout={event=>{
  const {y,height}=event.nativeEvent.layout;register?.(itemKey(row),y,height);
  if(lastY.current!==null&&lastY.current!==y&&!reduce.current&&Platform.OS==="web"){
   offset.stopAnimation();offset.setValue(lastY.current-y);Animated.timing(offset,{toValue:0,duration:180,useNativeDriver:false}).start();
  }lastY.current=y;
 }} pointerEvents={leaving?"none":"auto"} style={{opacity,transform:[{translateY:offset}],backgroundColor:highlight.interpolate({inputRange:[0,1],outputRange:["transparent",tint(theme.colors.accent,"20")]})}}>{children}</Animated.View>;
}
