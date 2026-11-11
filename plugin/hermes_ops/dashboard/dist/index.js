(function(){'use strict';
 const SDK=window.__HERMES_PLUGIN_SDK__;
 const {React}=SDK;
 function OperationsPage(){
  const [html,setHtml]=React.useState(null);
  const [error,setError]=React.useState('');
  React.useEffect(()=>{let active=true;
   SDK.authedFetch('/api/plugins/agentic-operations/ui')
    .then(response=>{if(!response.ok)throw new Error('Operations could not load (HTTP '+response.status+').');return response.text();})
    .then(text=>{if(active)setHtml(text);})
    .catch(err=>{if(active)setError(err.message);});
   return()=>{active=false;};
  },[]);
  if(error)return React.createElement('div',{role:'alert',style:{padding:24}},error);
  if(!html)return React.createElement('div',{role:'status',style:{padding:24}},'Loading operations…');
  return React.createElement('iframe',{title:'Orange operations workspace',srcDoc:html,style:{width:'100%',height:'calc(100dvh - 100px)',minHeight:560,border:0,display:'block'}});
 }
 window.__HERMES_PLUGINS__.register('agentic-operations',OperationsPage);
})();
