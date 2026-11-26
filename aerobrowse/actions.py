"""Isolated-world action map: validation and DOM activation occur in one renderer task.

Actions are synthetic DOM operations. They never substitute an ordinal/selector and
are deliberately unavailable for sites requiring trusted physical input.
"""

import json
from typing import Any

from aerobrowse.errors import AeroError

# Page scripts cannot access this isolated execution context or replace its builtins.
INSTALL = r"""(() => {
const state = {generation:'', epoch:0, captured:0, nodes:new Map(), document, url:location.href};
const observer = new MutationObserver(records => {state.epoch += records.length});
observer.observe(document, {subtree:true,childList:true,attributes:true,characterData:true});
const epoch = () => {state.epoch += observer.takeRecords().length;return state.epoch};
const visible = el => {const s=getComputedStyle(el);return el.isConnected && el.getClientRects().length>0 && s.display!=='none' && s.visibility!=='hidden' && !el.closest('[hidden],[inert],[aria-hidden="true"]')};
const disabled = el => el.matches(':disabled') || el.getAttribute('aria-disabled')==='true';
const safeURL = raw => {try {const u=new URL(raw,location.href);if(!['http:','https:'].includes(u.protocol))return '';u.username='';u.password='';u.search='';u.hash='';return u.href}catch{return ''}};
const metadata = el => {
 const tag=el.tagName.toLowerCase(),type=el.getAttribute('type')||'';
 const referenced=(el.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean).map(id=>document.getElementById(id)?.textContent||'').join(' ');
 const labels=Array.from(el.labels||[]).map(label=>{const copy=label.cloneNode(true);copy.querySelectorAll('input,textarea,select,button').forEach(n=>n.remove());return copy.textContent}).join(' ');
 const label=(el.getAttribute('aria-label')||referenced||labels||el.textContent||el.getAttribute('alt')||el.getAttribute('title')||el.getAttribute('placeholder')||'').trim();
 const role=el.getAttribute('role')||({a:'link',button:'button',textarea:'textbox',select:'combobox',summary:'button'}[tag])||(tag==='input'?(type==='checkbox'?'checkbox':type==='radio'?'radio':'textbox'):'');
 return {tag,element_type:tag,label,accessible_name:label,role,input_type:type,disabled:disabled(el),visible:visible(el),value:null,checked:typeof el.checked==='boolean'?el.checked:null,href:el.hasAttribute('href')?safeURL(el.getAttribute('href')):'',name:el.getAttribute('name')||'',attributes:{required:el.hasAttribute('required'),readonly:el.hasAttribute('readonly'),multiple:el.hasAttribute('multiple')}};
};
const selector='a[href],button,input:not([type="hidden"]),textarea,select,summary,[role="button"],[role="link"],[role="textbox"],[role="checkbox"],[role="combobox"],[role="radio"],[role="switch"],[role="menuitem"],[contenteditable="true"]';
const check = (entry,generation) => {
 if(state.document!==document || state.url!==location.href)return 'PAGE_NAVIGATED';
 if(generation!==state.generation)return 'STALE_ACTION_ID';
 if(!entry || !entry.node.isConnected || entry.node.ownerDocument!==document)return 'STALE_ACTION_ID';
 if(epoch()!==state.captured)return 'STALE_ACTION_ID';
 if(!visible(entry.node))return 'ELEMENT_NOT_VISIBLE';
 if(disabled(entry.node))return 'ELEMENT_DISABLED';
 if(JSON.stringify(metadata(entry.node))!==entry.fingerprint)return 'STALE_ACTION_ID';
 return null;
};
const fail = code => ({success:false,error:{code,message:'Action target state no longer matches the active snapshot'}});
const nativeSubmit=HTMLFormElement.prototype.requestSubmit;
const nativeClick=HTMLElement.prototype.click;
const nativeFocus=HTMLElement.prototype.focus;
const dispatch=EventTarget.prototype.dispatchEvent;
const send=(el,type)=>dispatch.call(el,new Event(type,{bubbles:true,composed:true}));
const setValue=(el,value)=>{const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value)};
state.snapshot = (generation,limit) => {
 state.generation=generation;state.nodes.clear();state.url=location.href;
 const actions=[];
 for(const node of document.querySelectorAll(selector)){
  if(!visible(node))continue;
  const data=metadata(node),id=generation+':'+(actions.length+1);
  state.nodes.set(id,{node,fingerprint:JSON.stringify(data)});
  actions.push({...data,id,generation,executable:!data.disabled});
 }
 state.captured=epoch();const html=document.documentElement.outerHTML;if(new TextEncoder().encode(html).length>limit)return {error:'HTML_TOO_LARGE'};return {actions,url:state.url,html};
};
state.perform = args => {
 const entry=state.nodes.get(args.id),error=check(entry,args.generation);if(error)return fail(error);
 const el=entry.node,op=args.operation,value=args.value;
 if(op==='wait')return {success:true};
 if(op==='click'){nativeClick.call(el);return {success:true,input_mode:'synthetic_dom'}};
 if(op==='fill'){
  if(!['INPUT','TEXTAREA'].includes(el.tagName)||el.readOnly||['checkbox','radio','file','button','submit','reset','hidden'].includes(el.type))return fail('ACTION_TYPE_MISMATCH');
  nativeFocus.call(el);const after=check(entry,args.generation);if(after)return fail(after);
  setValue(el,value);send(el,'input');return {success:true,input_mode:'synthetic_dom'};
 }
 if(op==='select'){
  if(el.tagName!=='SELECT'||![...el.options].some(o=>o.value===value&&!o.disabled))return fail('ACTION_TYPE_MISMATCH');
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(el,value);send(el,'change');return {success:true,input_mode:'synthetic_dom'};
 }
 if(op==='check'){
  if(el.tagName!=='INPUT'||!['checkbox','radio'].includes(el.type))return fail('ACTION_TYPE_MISMATCH');
  if(el.type==='radio'&&!value)return fail('UNSUPPORTED_CAPABILITY');
  if(el.checked!==value)nativeClick.call(el);return {success:true,input_mode:'synthetic_dom'};
 }
 if(op==='press'){
  if(!['Enter','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(value))return fail('UNSUPPORTED_CAPABILITY');
  nativeFocus.call(el);const after=check(entry,args.generation);if(after)return fail(after);
  const accepted=dispatch.call(el,new KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true}));
  if(!el.isConnected||state.document!==document||epoch()!==state.captured)return fail('STALE_ACTION_ID');
  if(accepted && value==='Enter' && el.tagName==='INPUT' && el.form && !['button','submit','reset','file','checkbox','radio'].includes(el.type)){
   const submitter=[...el.form.elements].find(n=>n.type==='submit'&&!n.disabled);
   if(submitter)nativeClick.call(submitter);else nativeSubmit.call(el.form);
   return {success:true,input_mode:'synthetic_dom'};
  }
  dispatch.call(el,new KeyboardEvent('keyup',{key:value,bubbles:true}));
  return {success:true,input_mode:'synthetic_dom'};
 }
 return fail('UNSUPPORTED_OPERATION');
};
state.dispose=()=>observer.disconnect();
return state;
})()"""


class ActionContext:
    """Own one CDP isolated context. Values are always JSON serialized."""

    def __init__(self, page: Any):
        self.page = page
        self.session = page.context.new_cdp_session(page)
        frame = self.session.send("Page.getFrameTree")["frameTree"]["frame"]["id"]
        self.context_id = self.session.send(
            "Page.createIsolatedWorld",
            {"frameId": frame, "worldName": "AeroBrowse actions"},
        )["executionContextId"]
        self._evaluate("globalThis.__aeroState = " + INSTALL + "; true")

    def _evaluate(self, expression: str) -> Any:
        result = self.session.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "contextId": self.context_id,
                "returnByValue": True,
            },
        )
        if result.get("exceptionDetails"):
            raise AeroError(
                "ACTION_CONTEXT_FAILED", "Isolated browser action context failed"
            )
        return result.get("result", {}).get("value")

    def snapshot(self, generation: str, html_limit: int = 5_000_000) -> dict[str, Any]:
        return self._evaluate(
            "globalThis.__aeroState.snapshot("
            + json.dumps(generation)
            + ","
            + str(html_limit)
            + ")"
        )

    def perform(
        self, action_id: str, generation: str, operation: str, value: Any
    ) -> dict[str, Any]:
        arguments = json.dumps(
            {
                "id": action_id,
                "generation": generation,
                "operation": operation,
                "value": value,
            }
        )
        return self._evaluate("globalThis.__aeroState.perform(" + arguments + ")")

    def close(self) -> None:
        try:
            self._evaluate("globalThis.__aeroState.dispose();true")
        finally:
            self.session.detach()
