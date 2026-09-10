import React from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

export const tint = (color: string, alpha = "20") => /^#[\da-f]{6}$/i.test(color) ? `${color}${alpha}` : color;
export function Badge({label,theme}:{label:string;theme:any}) {
  return <View style={{alignSelf:"flex-start",paddingHorizontal:9,paddingVertical:4,borderRadius:20,backgroundColor:tint(theme.colors.accent,"16")}}><Text style={{color:theme.colors.accent,fontSize:11,fontWeight:"700",letterSpacing:.3}}>{label}</Text></View>;
}
export function Card({children,theme}:{children:React.ReactNode;theme:any}) {
  return <View style={{padding:20,gap:12,borderRadius:16,borderWidth:1,borderColor:tint(theme.colors.foregroundMuted,"28"),backgroundColor:theme.colors.surface0}}>{children}</View>;
}
export function EmptyState({title,detail,theme}:{title:string;detail:string;theme:any}) {
  return <View style={{padding:28,gap:8,alignItems:"center",borderRadius:16,borderWidth:1,borderStyle:"dashed",borderColor:tint(theme.colors.foregroundMuted,"40")}}><Text style={{color:theme.colors.accent,fontSize:24}}>◇</Text><Text style={{color:theme.colors.foreground,fontWeight:"600",fontSize:16}}>{title}</Text><Text style={{color:theme.colors.foregroundMuted,lineHeight:21,textAlign:"center",maxWidth:440}}>{detail}</Text></View>;
}
export function Action({label,onPress,disabled=false,theme}:{label:string;onPress:()=>void;disabled?:boolean;theme:any}) {
  return <Pressable accessibilityRole="button" accessibilityState={{disabled}} disabled={disabled} onPress={onPress} style={({pressed})=>({paddingVertical:10,paddingHorizontal:14,borderRadius:10,borderWidth:1,borderColor:tint(theme.colors.foregroundMuted,"30"),backgroundColor:pressed?tint(theme.colors.accent,"24"):theme.colors.surface0,opacity:disabled?.45:1,transform:[{scale:pressed?.985:1}]})}><Text style={{color:theme.colors.foreground,fontSize:13,fontWeight:"600"}}>{label}</Text></Pressable>;
}
export function Loading({theme}:{theme:any}) {return <View accessibilityLiveRegion="polite" style={{padding:28,gap:12,alignItems:"center"}}><ActivityIndicator color={theme.colors.accent}/><Text style={{color:theme.colors.foregroundMuted}}>기록을 불러오는 중</Text></View>;}
