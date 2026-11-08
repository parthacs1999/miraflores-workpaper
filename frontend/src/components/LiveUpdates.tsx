"use client";
import {useEffect,useRef,useState} from 'react';
import {apiFetch} from './session';
import {EVIDENCE_API,evidenceButton as button,evidenceRequest} from './evidence-types';

type Change={document_ids:string[];finding_id:string|null;adjustment_id:string|null;review_status:string|null;id:number;resource_id:string;category:string;areas:string[];action:string;actor_id:string;created_at:string};
type Batch={events:Change[];cursor:number;has_more:boolean;checkpoint:{cursor:number;revision:number};scope_hash:string};

export default function LiveUpdates({refresh}:{refresh:()=>void}){
 const [events,setEvents]=useState<Change[]>([]);const [connected,setConnected]=useState(false);const [paused,setPaused]=useState(false);const [error,setError]=useState('');const [seen,setSeen]=useState({cursor:0,revision:0});const [marking,setMarking]=useState(false);const [attempt,setAttempt]=useState(0);
 const cursor=useRef<number|undefined>(undefined);const scope=useRef('');
 useEffect(()=>{
  if(paused)return;
  const controller=new AbortController();let retryTimer:ReturnType<typeof setTimeout>|undefined;
  let live=true;let handshake=true;
  async function poll(){
   while(live){
    try{
     const query=new URLSearchParams({wait_seconds:handshake?'0':'10',limit:'100'});if(cursor.current!==undefined)query.set('after',String(cursor.current));
     const response=await apiFetch(EVIDENCE_API+'/api/product/changes?'+query,{signal:controller.signal});
     const batch=await response.json();if(!response.ok){if(response.status===401||response.status===403){setEvents([]);cursor.current=undefined;scope.current='';window.dispatchEvent(new CustomEvent('workpaper:access-lost'));}throw new Error(batch.detail??'Live updates unavailable');}
     const b=batch as Batch;if(!live)return;
     if(scope.current&&scope.current!==b.scope_hash){cursor.current=undefined;scope.current=b.scope_hash;setEvents([]);continue;}
     scope.current=b.scope_hash;cursor.current=b.cursor;handshake=false;setConnected(true);setError('');
     setSeen(old=>b.checkpoint.revision>=old.revision?b.checkpoint:old);
     if(b.events.length){setEvents(old=>[...new Map([...old,...b.events].map(e=>[e.id,e])).values()].slice(-300));window.dispatchEvent(new CustomEvent('workpaper:changes'));}
    }catch(e){
     if(!live)return;handshake=true;setConnected(false);setError(String(e));
     // The last delivered cursor is retained. A retry never skips a missed page.
     await new Promise<void>(resolve=>{retryTimer=setTimeout(resolve,2000);controller.signal.addEventListener('abort',()=>resolve(),{once:true});});
    }
   }
  }
  void poll();return()=>{live=false;controller.abort();if(retryTimer)clearTimeout(retryTimer);};
 },[paused,attempt]);
 async function mark(){setMarking(true);try{const cp=await evidenceRequest<{cursor:number;revision:number}>('/api/product/checkpoint',{cursor:cursor.current??seen.cursor,expected_revision:seen.revision});setSeen(cp);setEvents(old=>old.filter(e=>e.id>cp.cursor));setError('');}catch(e){setError(String(e));}finally{setMarking(false);}}
 const unseen=events.filter(e=>e.id>seen.cursor);const categories=[...new Set(unseen.map(e=>e.category))];const areas=[...new Set(unseen.flatMap(e=>e.areas))];const documents=[...new Set(unseen.flatMap(e=>e.document_ids))];const findings=[...new Set(unseen.map(e=>e.finding_id).filter(Boolean))];const adjustments=[...new Set(unseen.map(e=>e.adjustment_id).filter(Boolean))];
 return <aside className="rounded-lg border border-indigo-200 bg-white p-3 text-sm" data-testid="live-updates" aria-label="Live workpaper changes"><div className="flex flex-wrap items-center gap-2"><strong>Since I last looked</strong><span data-testid="live-connection">{paused?'Paused':connected?'Live · reconnect recovery active':'Connecting / reconnecting…'}</span><button className={button} onClick={()=>{setPaused(v=>!v);setConnected(false);}}>{paused?'Reconnect live updates':'Pause live updates'}</button><button className={button} onClick={refresh}>Refresh current workspace</button><button className={button} disabled={marking||!connected} onClick={()=>void mark()}>Mark displayed changes seen</button></div><p>Personal checkpoint: {seen.cursor}. {unseen.length} retained changes since your checkpoint. Feed pages are recovered in order; this panel retains the most recent 300.</p>{error&&<p role="alert">{error}<button className={button} onClick={()=>setAttempt(v=>v+1)}>Retry live connection</button></p>}{unseen.length>0&&<details><summary>Change summaries · {areas.join(', ')} · {categories.join(', ')}</summary><p>Documents: {documents.join(', ')||'none in this page'} · Findings: {findings.length} · Adjustments: {adjustments.length}</p><ul className="max-h-64 overflow-auto">{unseen.map(e=><li key={e.id} data-testid="live-change" className="border-t py-1">{e.areas.join(', ')} · {e.category} · {e.action} · {e.resource_id} · documents {e.document_ids.join(', ')||'not linked'} · {e.actor_id} · {e.created_at}</li>)}</ul></details>}<p className="text-xs">Metadata only. Open the authorized workpaper for source values. Refreshing replaces open views; save edits first.</p></aside>;
}
