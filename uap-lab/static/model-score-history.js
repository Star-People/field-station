'use strict';
(()=>{
 const names={human:'Stable',experimental:'Experimental',hybrid:'Hybrid',machine:'Machine-only'};
 const ns='http://www.w3.org/2000/svg';let last=[],signature='';
 const svg=(tag,attrs,text)=>{const el=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el};
 function render(points){
  const leaderboard=document.getElementById('model-leaderboard');if(!leaderboard)return;
  let card=document.getElementById('modelScoreHistory');
  if(!card){card=document.createElement('section');card.id='modelScoreHistory';card.className='metrics-card model-comparison-card';card.innerHTML='<h2>Model score history</h2><div class="metrics-legend score-history-legend"></div><svg class="score-history-chart" role="img" aria-label="Model composite scores out of 100 over time"></svg><p class="score-history-empty" hidden>No scored comparisons in this period.</p>';leaderboard.closest('.metrics-card').after(card);
   const style=document.createElement('style');style.textContent='#modelScoreHistory{min-width:0}.score-history-chart{display:block;width:100%;height:250px;overflow:visible}.score-history-chart text{font:10px var(--app-font);fill:var(--muted)}.score-history-chart .grid{stroke:var(--line);stroke-width:1}.score-history-chart .score-line{fill:none;stroke:var(--ink);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}.score-history-chart .experimental{stroke-dasharray:7 4}.score-history-chart .hybrid{stroke-dasharray:2 4}.score-history-chart .machine{stroke-dasharray:10 3 2 3}.score-history-chart .score-hit{fill:transparent;stroke:none;cursor:crosshair}.score-history-chart .score-hit:focus{outline:none;stroke:var(--ink)}.score-history-legend{display:flex;flex-wrap:wrap;gap:16px}.score-history-legend span{display:inline-flex;gap:6px;align-items:center}.score-history-legend i{display:block;width:22px;height:0;border:0;border-radius:0;background:none;border-top:2px solid var(--ink)}.score-history-legend .experimental i{border-top-style:dashed}.score-history-legend .hybrid i{border-top-style:dotted}.score-history-legend .machine i{border-top-style:double;border-top-width:3px}';document.head.append(style);
   for(const [lane,name]of Object.entries(names)){const label=document.createElement('span');label.className=lane;const marker=document.createElement('i');marker.setAttribute('aria-hidden','true');label.append(marker,document.createTextNode(name));card.querySelector('.score-history-legend').append(label)}
  }
  const chart=card.querySelector('svg'),width=Math.max(280,chart.clientWidth||960),left=40,right=width-12,top=12,bottom=210;
  const rows=points.map(p=>({...p,time:p.epoch?p.epoch*1000:Date.parse(p.day+'T12:00:00Z')})).filter(p=>Number.isFinite(p.time)).sort((a,b)=>a.time-b.time);
  const next=JSON.stringify([width,rows]);if(next===signature)return;signature=next;chart.replaceChildren();chart.setAttribute('viewBox',`0 0 ${width} 250`);
  for(let n=0;n<=100;n+=25){const y=bottom-n/100*(bottom-top);chart.append(svg('line',{x1:left,x2:right,y1:y,y2:y,class:'grid'}),svg('text',{x:left-8,y:y+4,'text-anchor':'end'},n))}
  const first=rows[0]?.time,last=rows.at(-1)?.time,x=t=>first===last?(left+right)/2:left+(t-first)/(last-first)*(right-left),y=v=>bottom-v/100*(bottom-top);
  let tip=document.getElementById('scoreHistoryTooltip');if(!tip){tip=document.createElement('div');tip.id='scoreHistoryTooltip';tip.className='model-chart-tooltip';tip.setAttribute('role','status');document.body.append(tip)}tip.hidden=true;
  const hide=()=>{tip.hidden=true};chart.onpointerleave=hide;
  function show(row,clientX,clientY){tip.replaceChildren();const title=document.createElement('strong');title.textContent=new Date(row.time).toLocaleString();tip.append(title);for(const [lane,name]of Object.entries(names)){const score=scoreFor(row,lane),line=document.createElement('div');line.textContent=name+': '+(score===null?'Not measured':score.toFixed(1)+' / 100')+' · '+(row[lane+'_version']||'').slice(0,8);tip.append(line)}tip.hidden=false;tip.style.left=Math.max(12,Math.min(innerWidth-tip.offsetWidth-12,clientX+12))+'px';tip.style.top=Math.max(12,Math.min(innerHeight-tip.offsetHeight-12,clientY-tip.offsetHeight-12))+'px'}
  let count=0;
  for(const lane of Object.keys(names)){let d='',connected=false;const hits=[];
   for(const row of rows){const score=scoreFor(row,lane);if(score===null){connected=false;continue}count++;d+=(connected?' L':' M')+x(row.time)+','+y(score);connected=true;const dot=svg('circle',{cx:x(row.time),cy:y(score),r:8,class:'score-hit',tabindex:0,'aria-label':`${names[lane]}: ${score.toFixed(1)} out of 100, ${new Date(row.time).toLocaleString()}`});dot.onfocus=()=>{const r=dot.getBoundingClientRect();show(row,r.x,r.y)};dot.onblur=hide;dot.onpointerenter=e=>show(row,e.clientX,e.clientY);hits.push(dot)}
   chart.append(svg('path',{d,class:'score-line '+lane}));for(const hit of hits)chart.append(hit);
  }
  chart.onpointermove=e=>{if(!rows.length||!count)return;const r=chart.getBoundingClientRect(),px=(e.clientX-r.left)/r.width*width;const row=rows.reduce((best,p)=>Math.abs(x(p.time)-px)<Math.abs(x(best.time)-px)?p:best,rows[0]);show(row,e.clientX,e.clientY)};
  card.querySelector('.score-history-empty').hidden=count>0;
  if(rows.length){const ticks=first===last?1:(width<500?3:6);for(let i=0;i<ticks;i++){const time=ticks===1?first:first+i*(last-first)/(ticks-1);chart.append(svg('text',{x:x(time),y:238,'text-anchor':i===0?'start':i===ticks-1?'end':'middle'},new Date(time).toLocaleDateString(undefined,{month:'short',day:'numeric'})))}}

 }
 function scoreFor(row,lane){const score=modelComposite(row.lanes?.[lane]);if(!score)return null;const support=Object.keys(names).map(k=>modelComposite(row.lanes?.[k])).find(Boolean);return score.positive===support.positive&&score.negative===support.negative?score.score:null}
 window.addEventListener('station-score-history',e=>{last=e.detail.points;render(last)});
})();
