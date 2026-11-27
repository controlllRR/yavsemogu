
(()=>{'use strict';
const $=id=>document.getElementById(id);
// Панель настроек по умолчанию скрыта. Открывается кнопкой без PIN-кода.
let teacherOpen=false;
const launch=$('teacherLaunch'),drawer=$('controls'),shade=$('teacherShade');
function unlockUI(){
 teacherOpen=true;
 shade.hidden=false;
 drawer.classList.add('is-open');
 drawer.removeAttribute('inert');
 drawer.setAttribute('aria-hidden','false');
 launch.setAttribute('aria-expanded','true');
 $('teacherClose').focus();
}
function lockUI(){
 teacherOpen=false;
 drawer.classList.remove('is-open');
 drawer.setAttribute('aria-hidden','true');
 drawer.setAttribute('inert','');
 shade.hidden=true;
 launch.setAttribute('aria-expanded','false');
 launch.focus();
}
launch.addEventListener('click',()=>{if(teacherOpen)lockUI();else unlockUI();});
$('teacherClose').addEventListener('click',lockUI);
$('teacherLock').addEventListener('click',lockUI);
shade.addEventListener('click',lockUI);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&teacherOpen)lockUI();});

const svg=$('board'),NS='http://www.w3.org/2000/svg',pieces=$('coloredSegments'),ghost=$('ghost'),head=$('head'),headGlow=$('headGlow'),finger=$('traceFinger'),drawPath=$('drawPath');
const FULL=1000,HEIGHT=540,MINX=70,MAXX=930,MINY=55,MAXY=460;
const make=(name,attrs={})=>{const n=document.createElementNS(NS,name);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));return n};
for(let x=100;x<1000;x+=100){$('grid').append(make('line',{x1:x,y1:20,x2:x,y2:490}));}
for(let y=80;y<500;y+=80){$('grid').append(make('line',{x1:25,y1:y,x2:975,y2:y}));}
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),lerp=(a,b,t)=>a+(b-a)*t,dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y),pathText=pts=>'M '+pts.map(p=>`${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' L ');
let custom=[],points=[],arc=[],totalLen=0,visualSections=[],shapeID='zigzag',lastNonCustomShape='zigzag';
let mode='class',playing=false,paused=false,finished=false,editing=false,round=0,roundLimit=10,elapsed=0,roundLength=6,lastFrame=0,raf=0,nextTimer=0,score=0,traceSamples=[],pointerDown=false,editPoints=[],editPointer=false,waitNext=false;
let beatIndex=0,accentIndex=0,beatsPerRound=12,beatSeconds=.5,accents=[],previewInterval=0,previewIndex=0,previewStart=0,audioCtx=null,master=null,noiseBuffer=null,classicAudio=null;
const soundClass=window.AudioContext||window.webkitAudioContext;
const SHAPES=['hemi','zigzag','wave','hills','steps','loops','spiral','eight','heart','star','flower'];
const SHAPE_NAMES={hemi:'Два зигзага',zigzag:'Зигзаг',wave:'Волна',hills:'Горки',steps:'Лесенка',loops:'Петли',spiral:'Спираль',eight:'Восьмёрка',heart:'Сердце',star:'Звезда',flower:'Цветок',custom:'Своя линия'};
const isClassic=v=>String(v||'').startsWith('classic:');
const classicId=v=>String(v||'').slice(8);
const note=(name)=> { const map={C:0,'C#':1,D:2,'D#':3,E:4,F:5,'F#':6,G:7,'G#':8,A:9,'A#':10,B:11};const m=/^([A-G]#?)(\d)$/.exec(name);return m?440*Math.pow(2,((Number(m[2])+1)*12+map[m[1]]-69)/12):440;};
try{let saved=JSON.parse(localStorage.getItem('linesRhythmCustomV2')||'[]');if(Array.isArray(saved)&&saved.length>3&&saved.length<5000)custom=saved.filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)).map(p=>({x:clamp(p.x,10,990),y:clamp(p.y,10,530)}));}catch{}
function difficulty(){return {easy:0,normal:1,hard:2}[$('difficulty').value]||0;}
function generate(id){const d=difficulty(),out=[];
 const many=(n,fn)=>{for(let i=0;i<=n;i++)out.push(fn(i/n,i));};
 if(id==='hemi'){const n=[4,6,8][d],dx=(MAXX-MINX)/n;out.push({x:MINX,y:200});for(let i=1;i<=n;i++)out.push({x:MINX+i*dx,y:i%2?95:205});out.push({x:MAXX,y:205});out.push({x:MINX,y:360});for(let i=1;i<=n;i++)out.push({x:MINX+i*dx,y:i%2?455:355});}
 else if(id==='zigzag'){const n=[4,6,9][d],dx=(MAXX-MINX)/n;out.push({x:MINX,y:390});for(let i=1;i<=n;i++)out.push({x:MINX+i*dx,y:i%2?115+(Math.random()-.5)*55:390+(Math.random()-.5)*55});}
 else if(id==='wave'){const turns=[2,3,5][d];many(260,t=>({x:MINX+860*t,y:270+150*Math.sin(2*Math.PI*turns*t)}));}
 else if(id==='hills'){const count=[2,3,5][d];many(240,t=>({x:MINX+860*t,y:400-270*Math.abs(Math.sin(Math.PI*count*t))}));}
 else if(id==='steps'){const n=[4,6,9][d],start=420;out.push({x:MINX,y:start});for(let i=0;i<n;i++){const xx=MINX+860*(i+1)/n;out.push({x:xx,y:out[out.length-1].y});out.push({x:xx,y:i%2===0?130:420});}}
 else if(id==='loops'){let count=[2,3,4][d];many(320,t=>({x:85+830*t+48*Math.sin(2*Math.PI*count*t),y:270+145*Math.sin(2*Math.PI*count*t+Math.PI/3)}));}
 else if(id==='spiral'){const turns=[2,3,4][d];many(400,t=>{const a=t*2*Math.PI*turns;const r=14+192*t;return{x:500+r*Math.cos(a),y:270+r*Math.sin(a)};});}
 else if(id==='eight'){const turns=[1,2,3][d];many(360,t=>{const a=t*2*Math.PI*turns;return{x:500+285*Math.sin(a),y:270+166*Math.sin(2*a)};});}
 else if(id==='heart'){many(310,t=>{const a=2*Math.PI*t;return{x:500+17*16*Math.pow(Math.sin(a),3),y:278-12.5*(13*Math.cos(a)-5*Math.cos(2*a)-2*Math.cos(3*a)-Math.cos(4*a))};});}
 else if(id==='star'){const stars=[5,7,9][d],r=205;for(let i=0;i<=stars;i++){const a=-Math.PI/2+i*2*Math.PI*2/stars;out.push({x:500+r*Math.cos(a),y:269+r*Math.sin(a)});}}
 else if(id==='flower'){const petals=[4,5,7][d];many(400,t=>{const a=t*2*Math.PI,r=126+65*Math.cos(petals*a);return{x:500+r*Math.cos(a),y:270+r*Math.sin(a)};});}
 else if(id==='custom'&&custom.length>2){return custom.map(p=>({...p}));}
 return out;
}
function chooseShape(){if(mode==='hemi')return 'hemi';const chosen=$('shape').value;if(chosen==='random')return SHAPES.filter(s=>s!=='hemi')[Math.floor(Math.random()*(SHAPES.length-1))];if(chosen==='custom'&&custom.length<3)return 'wave';return chosen;}
function normalizePath(pts){const clean=[];for(const p of pts){if(Number.isFinite(p.x)&&Number.isFinite(p.y)&&(!clean.length||dist(p,clean[clean.length-1])>=.8))clean.push({x:p.x,y:p.y});}if(clean.length<2)return [{x:70,y:270},{x:930,y:270}];return clean;}
function rebuildArc(){arc=[0];totalLen=0;for(let i=1;i<points.length;i++){totalLen+=dist(points[i-1],points[i]);arc.push(totalLen);}totalLen=Math.max(1,totalLen);}
function atDistance(len){len=clamp(len,0,totalLen);let lo=0,hi=arc.length-1;while(lo<hi){const mid=(lo+hi)>>1;if(arc[mid]<len)lo=mid+1;else hi=mid;}const i=Math.max(1,lo),prev=arc[i-1],t=(len-prev)/Math.max(.001,arc[i]-prev);return{x:lerp(points[i-1].x,points[i].x,clamp(t,0,1)),y:lerp(points[i-1].y,points[i].y,clamp(t,0,1))};}
function sectionCount(id){if(id==='hemi')return [8,12,16][difficulty()];if(id==='custom')return clamp(Math.round(totalLen/210),4,14);if(id==='zigzag')return [4,6,9][difficulty()];if(id==='steps')return [4,6,9][difficulty()];return [6,8,12][difficulty()];}
function segColor(i,n){const style=mode==='hemi'?'half':$('colorStyle').value;if(style==='single')return '#d4a5e8';if(style==='alternate')return i%2?'#9bb8e0':'#e8a0c0';if(style==='rainbow')return ['#e8a0c0','#e8c49a','#d4d48a','#9dceb8','#9bb8e0','#b5a0d4'][i%6];return i<n/2?'#e8a0c0':'#9bb8e0';}
function computeLine(){shapeID=chooseShape();points=normalizePath(generate(shapeID));rebuildArc();const n=sectionCount(shapeID);visualSections=[];pieces.replaceChildren();
 for(let i=0;i<n;i++){let pts=[atDistance(totalLen*i/n)];for(let j=1;j<points.length-1;j++){let s=arc[j]/totalLen;if(s>i/n&&s<(i+1)/n)pts.push(points[j]);}pts.push(atDistance(totalLen*(i+1)/n));const el=make('path',{d:pathText(pts),stroke:segColor(i,n),'stroke-width':13,fill:'none','stroke-linecap':'round','stroke-linejoin':'round'});pieces.append(el);let length=pts.slice(1).reduce((acc,p,j)=>acc+dist(p,pts[j]),0);el.style.strokeDasharray=length+' '+(length+4);el.style.strokeDashoffset=length;visualSections.push({el,length});}
 ghost.setAttribute('d',pathText(points));$('shapeName').textContent=SHAPE_NAMES[shapeID];head.setAttribute('visibility','visible');headGlow.setAttribute('visibility','visible');finger.setAttribute('visibility','hidden');traceSamples=[];pointerDown=false;
 accents=[];for(let i=1;i<n;i++)accents.push(i/n);if(shapeID==='star'||shapeID==='zigzag')for(let i=1;i<points.length-1;i++)accents.push(arc[i]/totalLen);accents=[...new Set(accents.map(a=>Number(a.toFixed(4))))].filter(x=>x>.01&&x<.99).sort((a,b)=>a-b);
 updateVisual(mode==='trace'?1:0);
}
function updateVisual(amount){const f=clamp(amount,0,1),scaled=f*visualSections.length;visualSections.forEach((s,i)=>{s.el.style.strokeDashoffset=s.length*(1-clamp(scaled-i,0,1));});const pt=atDistance(totalLen*f);head.setAttribute('cx',pt.x);head.setAttribute('cy',pt.y);headGlow.setAttribute('cx',pt.x);headGlow.setAttribute('cy',pt.y);const hideHead=mode==='trace';head.setAttribute('visibility',hideHead?'hidden':'visible');headGlow.setAttribute('visibility',hideHead?'hidden':'visible');}
function timeSettings(apply=true){
 const requested=Number($('duration').value);$('durationVal').textContent=requested+' с';$('volumeValue').textContent=$('volume').value+'%';
 const segments=sectionCount(shapeID),choices=[.5,1,2,3,4,6,8];let best={beats:12,penalty:Infinity};
 for(const multiple of choices){const n=Math.max(4,Math.round(segments*multiple)),bpm=60*n/requested;
 const penalty=Math.abs(Math.log(bpm/118))+(bpm<76||bpm>168?2:0)+(multiple<1?.06:0);
 if(penalty<best.penalty)best={beats:n,penalty};}
 const resultBpm=Math.round(60*best.beats/requested);
 $('bpmLabel').textContent=resultBpm+' BPM';
 if(apply){roundLength=requested;beatsPerRound=best.beats;beatSeconds=roundLength/beatsPerRound;}
}
function position(e){const matrix=svg.getScreenCTM();if(matrix&&window.DOMPoint){const pt=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());return{x:clamp(pt.x,0,FULL),y:clamp(pt.y,0,HEIGHT)};}const rect=svg.getBoundingClientRect();const scale=Math.min(rect.width/FULL,rect.height/HEIGHT),ox=(rect.width-scale*FULL)/2,oy=(rect.height-scale*HEIGHT)/2;return{x:clamp((e.clientX-rect.left-ox)/scale,0,FULL),y:clamp((e.clientY-rect.top-oy)/scale,0,HEIGHT)};}
function showOverlay(title,description,button){$('overlayTitle').textContent=title;$('overlayDesc').textContent=description;$('overlayAction').textContent=button;$('overlayAction').hidden=false;$('overlay').hidden=false;}
function stopTick(){cancelAnimationFrame(raf);clearTimeout(nextTimer);raf=0;nextTimer=0;}
function stopGame(){stopTick();playing=false;paused=false;finished=false;waitNext=false;stopPreview();silence();stopClassic();$('pauseBtn').disabled=true;$('pauseBtn').textContent='Ⅱ Пауза';if($('quickPause')){$('quickPause').disabled=true;$('quickPause').textContent='Пауза';}}
function startGame(){if(editing)exitEditor(false);stopGame();timeSettings();mode=$('mode').value;if(mode==='hemi'){$('shape').value='hemi';$('colorStyle').value='half';}roundLimit=Number($('rounds').value);playing=true;paused=false;round=0;score=0;$('scoreLabel').textContent=mode==='trace'?'Очки: 0':'Играй руками';$('pauseBtn').disabled=false;$('quickPause')&&($('quickPause').disabled=false);$('overlay').hidden=true;initSound();startClassic();startRound();lastFrame=performance.now();raf=requestAnimationFrame(tick);if(teacherOpen)lockUI();}
function startRound(){clearTimeout(nextTimer);waitNext=false;round++;elapsed=0;finished=false;mode=$('mode').value;computeLine();resetSoundRound();startClassic();$('roundLabel').textContent=`Раунд ${round} / ${roundLimit===999?'∞':roundLimit}`;$('stateLabel').textContent=mode==='trace'?'Обводи линию':mode==='hemi'?'Левая, потом правая':'Повторяй движение';$('timeLabel').textContent='0,0 с';$('canvasText').textContent=mode==='trace'?'Проведи пальцем по всей фигуре':mode==='hemi'?'Сначала левая рука (розовый), потом правая (голубой)':'Следи за белой точкой и двигай рукой';}
function tick(now){if(!playing)return;const delta=Math.min(.08,Math.max(0,(now-lastFrame)/1000));lastFrame=now;if(!paused&&!finished){elapsed+=delta;scheduleSound();if(mode==='class'||mode==='hemi')updateVisual(elapsed/roundLength);$('timeLabel').textContent=Math.min(roundLength,elapsed).toFixed(1).replace('.',',')+' с';if(elapsed>=roundLength)finishRound();}raf=requestAnimationFrame(tick);}
function closestPath(p){let best=Infinity,s=0;for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i],vx=b.x-a.x,vy=b.y-a.y,len2=vx*vx+vy*vy;if(len2<.001)continue;const t=clamp(((p.x-a.x)*vx+(p.y-a.y)*vy)/len2,0,1);const dd=Math.hypot(p.x-a.x-vx*t,p.y-a.y-vy*t);if(dd<best){best=dd;s=arc[i-1]+Math.sqrt(len2)*t;}}return {distance:best,progress:s/totalLen};}
function gradeTrace(){if(traceSamples.length<3)return 0;let total=0,hit=new Set(),lastProgress=0;const n=26;for(const p of traceSamples){const result=closestPath(p);total+=result.distance;if(result.distance<55){hit.add(Math.min(n-1,Math.floor(result.progress*n)));lastProgress=Math.max(lastProgress,result.progress);}}const accuracy=clamp(1-total/traceSamples.length/95,0,1);const coverage=hit.size/n;const sufficient=Math.min(1,traceSamples.length/18);return Math.round(100*accuracy*(.15+.85*coverage)*sufficient*(lastProgress>.9?1:.85));}
function finishRound(){if(finished||!playing)return;finished=true;silence();updateVisual(1);if(mode==='trace'){const earned=gradeTrace();score+=earned;$('scoreLabel').textContent='Очки: '+score+' (+'+earned+')';$('stateLabel').textContent=earned>=65?'Отлично!':'Попробуй ещё!';}else $('stateLabel').textContent='Здорово!';if(round>=roundLimit){playing=false;$('pauseBtn').disabled=true;stopTick();const doneMsg=mode==='trace'?`Набрано ${score} из ${roundLimit*100}. ${score>=roundLimit*70?'Супер точность!':'Ещё разок — и будет ещё лучше!'}`:`Пройдено ${round} раундов. Смени форму или музыку — и снова в ритм!`;showOverlay('Игра завершена!',doneMsg,'Играть снова');return;}
 nextTimer=setTimeout(()=>{if(!playing)return;if(paused)waitNext=true;else startRound();},700);}
function togglePause(){if(!playing||editing)return;paused=!paused;if(paused){silence();pauseClassic();showOverlay('Пауза','Музыка и линия остановлены. Можно продолжить.','▶ Продолжить');$('pauseBtn').textContent='▶ Продолжить';if($('quickPause'))$('quickPause').textContent='▶ Дальше';$('stateLabel').textContent='Пауза';}else{if(waitNext)startRound();resumeVolume();resumeClassic();$('overlay').hidden=true;$('pauseBtn').textContent='Ⅱ Пауза';if($('quickPause'))$('quickPause').textContent='Пауза';$('stateLabel').textContent=mode==='trace'?'Обводи линию':mode==='hemi'?'Левая, потом правая':'Повторяй движение';lastFrame=performance.now();}}
function enterEditor(){if(!teacherOpen)return;if($('shape').value!=='custom')lastNonCustomShape=$('shape').value;stopGame();editing=true;document.body.classList.add('editorActive');$('overlay').hidden=true;$('stateLabel').textContent='Режим рисования';$('roundLabel').textContent='Своя линия';pieces.replaceChildren();ghost.setAttribute('d','');head.setAttribute('visibility','hidden');headGlow.setAttribute('visibility','hidden');finger.setAttribute('visibility','hidden');editPoints=[];editPointer=false;drawPath.setAttribute('d','');drawPath.setAttribute('visibility','visible');$('canvasText').textContent='Нарисуй линию одним движением';$('editorHint').textContent='Нарисуй пальцем или мышью непрерывную линию. Начни где угодно.';}
function exitEditor(showStart=true){editing=false;document.body.classList.remove('editorActive');if(custom.length<3&&$('shape').value==='custom')$('shape').value=lastNonCustomShape;drawPath.setAttribute('visibility','hidden');editPointer=false;if(showStart){mode=$('mode').value;computeLine();showOverlay('Линия готова!','Можешь выбрать музыку и начать игру.','▶ Начать игру');$('roundLabel').textContent='Раунд 0 / '+$('rounds').value;$('stateLabel').textContent='Готов к игре';}}
function saveCustom(){if(editPoints.length<4||editPoints.reduce((acc,p,i)=>i?acc+dist(p,editPoints[i-1]):0,0)<120){$('editorHint').textContent='Нужно нарисовать более длинную линию одним непрерывным движением.';return;}
 // равномерно прореживаем запись движений, чтобы не нагружать браузер
 const trimmed=editPoints.filter((p,i)=>i===0||i===editPoints.length-1||i%2===0);custom=normalizePath(trimmed);try{localStorage.setItem('linesRhythmCustomV2',JSON.stringify(custom));}catch{}$('shape').value='custom';exitEditor(true);timeSettings();}
svg.addEventListener('pointerdown',e=>{if(editing){e.preventDefault();editPointer=true;editPoints=[];drawPath.setAttribute('d','');svg.setPointerCapture(e.pointerId);const p=position(e);editPoints.push(p);drawPath.setAttribute('d',pathText(editPoints));return;}
 if(mode!=='trace'||!playing||paused||finished)return;const p=position(e);if(traceSamples.length===0&&Math.hypot(p.x-points[0].x,p.y-points[0].y)>110)return;e.preventDefault();pointerDown=true;svg.setPointerCapture(e.pointerId);traceSamples.push(p);finger.setAttribute('cx',p.x);finger.setAttribute('cy',p.y);finger.setAttribute('visibility','visible');});
svg.addEventListener('pointermove',e=>{if(editing&&editPointer){e.preventDefault();const p=position(e);if(dist(p,editPoints[editPoints.length-1])>=3){editPoints.push(p);drawPath.setAttribute('d',pathText(editPoints));}return;}
 if(mode==='trace'&&pointerDown&&playing&&!paused&&!finished){e.preventDefault();const p=position(e);if(dist(p,traceSamples[traceSamples.length-1])>=2){traceSamples.push(p);finger.setAttribute('cx',p.x);finger.setAttribute('cy',p.y);}}});
const endPointer=()=>{editPointer=false;pointerDown=false;};svg.addEventListener('pointerup',endPointer);svg.addEventListener('pointercancel',endPointer);
$('drawBtn').onclick=enterEditor;$('clearBtn').onclick=()=>{editPoints=[];drawPath.setAttribute('d','');$('editorHint').textContent='Поле очищено. Нарисуй новую линию.';};$('saveBtn').onclick=saveCustom;$('cancelBtn').onclick=()=>exitEditor(true);
$('startBtn').onclick=startGame;$('restartBtn').onclick=startGame;$('overlayAction').onclick=()=>{if(playing&&paused)togglePause();else startGame();};$('pauseBtn').onclick=togglePause;
$('fullBtn').onclick=async()=>{const app=$('app');try{if(document.fullscreenElement)await document.exitFullscreen();else await app.requestFullscreen();}catch{document.body.classList.toggle('isFullscreen');}};
document.addEventListener('fullscreenchange',()=>document.body.classList.toggle('isFullscreen',!!document.fullscreenElement));
$('shape').onchange=()=>{if($('shape').value==='custom'&&custom.length<3){enterEditor();return;}if(!playing&&!editing){computeLine();updateVisual(1);timeSettings();}else if(playing)startGame();};
$('difficulty').onchange=()=>{if(!playing&&!editing){computeLine();updateVisual(1);timeSettings();}};
$('colorStyle').onchange=()=>{if(!playing&&!editing){computeLine();updateVisual(1);}else if(playing){visualSections.forEach((s,i)=>s.el.setAttribute('stroke',segColor(i,visualSections.length)));}};
$('mode').onchange=()=>{mode=$('mode').value;if(mode==='hemi'){$('shape').value='hemi';$('colorStyle').value='half';}$('modeNote').textContent=mode==='hemi'?'Два зигзага: сначала левая рука, потом правая продолжает.':'Подключи к телевизору или доске, выбери музыку и нажми «Старт».';if(playing)startGame();else if(!editing){computeLine();updateVisual(1);}};
$('rounds').onchange=()=>{if(!playing)$('roundLabel').textContent='Раунд 0 / '+($('rounds').value==='999'?'∞':$('rounds').value);};
$('duration').oninput=()=>timeSettings(!playing);$('volume').oninput=()=>{ $('volumeValue').textContent=$('volume').value+'%';resumeVolume();};
$('music').onchange=()=>{stopClassic();if(previewInterval){stopPreview();startPreview();}if(playing){resetSoundRound();startClassic();}$('musicNote').textContent=isClassic($('music').value)?'Классическая запись. Идёт вместе с линией.':$('music').value==='cues'?'Сигнал на каждом цветном переходе.':$('music').value==='off'?'Музыка выключена.':'Синтез в браузере. Ритм под линию.';resumeVolume();};
document.addEventListener('keydown',e=>{if(e.code==='Space'&&!['SELECT','BUTTON','INPUT','TEXTAREA'].includes(document.activeElement?.tagName)){e.preventDefault();if(playing)togglePause();else if(!editing)startGame();}});
function stopClassic(){if(!classicAudio)return;try{classicAudio.pause();classicAudio.currentTime=0;}catch{}classicAudio=null;}
function pauseClassic(){if(classicAudio)try{classicAudio.pause();}catch{}}
function resumeClassic(){if(!classicAudio||!isClassic($('music').value)||paused)return;classicAudio.volume=Number($('volume').value)/100;classicAudio.play().catch(()=>{});}
function startClassic(){stopClassic();const v=$('music').value;if(!isClassic(v)||!playing)return;const id=classicId(v);classicAudio=new Audio('assets/music/'+id+'.mp3');classicAudio.loop=true;classicAudio.volume=Number($('volume').value)/100;classicAudio.play().catch(()=>{$('musicNote').textContent='Не удалось запустить классику — разрешите звук в браузере.';});}
function initSound(){if(!soundClass)return false;try{if(!audioCtx){audioCtx=new soundClass();master=audioCtx.createGain();master.gain.value=0;const compressor=audioCtx.createDynamicsCompressor();compressor.threshold.value=-20;compressor.knee.value=10;compressor.ratio.value=5;compressor.attack.value=.002;compressor.release.value=.18;master.connect(compressor);compressor.connect(audioCtx.destination);noiseBuffer=audioCtx.createBuffer(1,Math.ceil(audioCtx.sampleRate*.4),audioCtx.sampleRate);const data=noiseBuffer.getChannelData(0);for(let i=0;i<data.length;i++)data[i]=Math.random()*2-1;}if(audioCtx.state==='suspended')audioCtx.resume().catch(()=>{});resumeVolume();return true;}catch(err){$('musicNote').textContent='В этом браузере звук недоступен. Без музыки игра продолжит работать.';return false;}}
function resumeVolume(){if(!audioCtx||!master)return;const synthOn=!isClassic($('music').value)&&($('music').value!=='off')&&((playing&&!paused&&!finished)||previewInterval);const volume=synthOn?Number($('volume').value)/100*.52:0;master.gain.setTargetAtTime(volume,audioCtx.currentTime,.015);if(classicAudio)classicAudio.volume=Number($('volume').value)/100;}
function silence(){if(audioCtx&&master)master.gain.setTargetAtTime(0,audioCtx.currentTime,.012);pauseClassic();}
function osc(freq,t,len=.16,amp=.09,wave='triangle',endFreq=0,lowpass=0){if(!audioCtx||!master)return;t=Math.max(t,audioCtx.currentTime);const source=audioCtx.createOscillator(),gain=audioCtx.createGain();source.type=wave;source.frequency.setValueAtTime(Math.max(25,freq),t);if(endFreq>0)source.frequency.exponentialRampToValueAtTime(endFreq,t+len);gain.gain.setValueAtTime(.0001,t);gain.gain.exponentialRampToValueAtTime(Math.max(.0002,amp),t+.009);gain.gain.exponentialRampToValueAtTime(.0001,t+len);source.connect(gain);if(lowpass){const filter=audioCtx.createBiquadFilter();filter.type='lowpass';filter.frequency.value=lowpass;gain.connect(filter);filter.connect(master);}else gain.connect(master);source.start(t);source.stop(t+len+.03);}
function noise(type,t,strength=1){if(!audioCtx||!noiseBuffer)return;t=Math.max(t,audioCtx.currentTime);const source=audioCtx.createBufferSource(),filter=audioCtx.createBiquadFilter(),gain=audioCtx.createGain();source.buffer=noiseBuffer;const settings={hat:[6000,.07,.064],snare:[1800,.15,.115],shaker:[4000,.10,.042],clap:[1200,.11,.14],softHat:[3500,.08,.022]};const [cut,len,v]=settings[type]||settings.hat;filter.type='highpass';filter.frequency.value=cut;gain.gain.setValueAtTime(Math.max(.0001,v*strength),t);gain.gain.exponentialRampToValueAtTime(.0001,t+len);source.connect(filter);filter.connect(gain);gain.connect(master);source.start(t);source.stop(t+len+.01);}
function drum(which,t,v=1){switch(which){case'kick':osc(150,t,.21,.27*v,'sine',46);break;case'snare':noise('snare',t,v);osc(200,t,.08,.038*v,'triangle',125);break;case'hat':noise('hat',t,v);break;case'shaker':noise('shaker',t,v);break;case'clap':noise('clap',t,v);break;case'wood':osc(730,t,.065,.080*v,'sine',480);break;case'conga':osc(220,t,.20,.13*v,'triangle',126);break;case'brush':noise('softHat',t,v);break;}}
function bell(midi,t,l=.19,v=.055){osc(note(midi),t,l,v,'sine');osc(note(midi)*2,t,l*.5,v*.20,'sine');}
function bass(midi,t,l=.25,v=.11){osc(note(midi),t,l,v,'triangle',0,850);}
function chord(notes,t,l=.4,v=.03){notes.forEach((n,i)=>osc(note(n),t+i*.009,l,v,'sine'));}
function playStyle(style,i,t,b){const k=i%16,q=i%8,m=i%4,s=i%3;
 if(style==='off'||style==='cues')return;
 if(style==='pop'){if(i%2===0)drum('kick',t,.80);else drum('snare',t,.65);drum('hat',t,.38);noise('hat',t+b/2,.20);bass(['C3','C3','A2','A2','F2','F2','G2','G2'][q],t,.24,.075);let melody=['E5','G5',null,'A5','G5',null,'D5','E5','G5','B5',null,'G5','E5','D5',null,'C5'][k];if(melody)bell(melody,t,.16,.062);}
 else if(style==='funk'){if([0,3,4,6].includes(q))drum('kick',t,.84);if(q===2||q===6)drum('snare',t,.92);drum('hat',t,.31);if(q%2===0)noise('hat',t+b*.65,.23);let f=['E3',null,'E3','G3','A3',null,'D3','E3'][q];if(f)bass(f,t,.16,.105);if([1,5,7].includes(q))osc(note('E4')*(q===5?1.5:1),t,.095,.035,'sawtooth',0,1600);}
 else if(style==='latin'){drum('shaker',t,.57);drum('shaker',t+b*.5,.44);if(q===0||q===3||q===5)drum('conga',t,.69);if(q===2||q===6)drum('wood',t,.60);if(q===0||q===4)drum('kick',t,.48);let f=['C3',null,'G3','C3',null,'G3','A2','G3'][q];if(f)bass(f,t,.15,.068);let melo=['E5','G5','C6',null,'A5','G5','E5',null][q];if(melo)bell(melo,t,.23,.060);}
 else if(style==='chip'){if(m===0)drum('kick',t,.44);if(m===2)drum('snare',t,.28);const arpeggio=['C5','E5','G5','C6','A4','C5','E5','A5','F4','A4','C5','F5','G4','B4','D5','G5'][k];osc(note(arpeggio),t,b*.62,.052,'square',0,2600);osc(note(arpeggio)*2,t+b*.50,b*.23,.026,'square',0,2200);if(i%2===0)bass(['C3','A2','F2','G2'][Math.floor(k/4)],t,b*.7,.058);}
 else if(style==='lofi'){if(m===0)drum('kick',t,.45);if(m===2)drum('snare',t,.27);drum('brush',t,.30);if(m===1)drum('brush',t+b*.55,.24);if(k%4===0)chord([['C4','E4','G4'],['A3','C4','E4'],['F3','A3','C4'],['G3','B3','D4']][Math.floor(k/4)],t,b*3,.018);let melo=['E5',null,'G5',null,'B4','C5',null,'G4'][q];if(melo)bell(melo,t,.35,.026);}
 else if(style==='techno'){drum('kick',t,.78);noise('hat',t+b*.5,.38);if(m===1||m===3)drum('clap',t,.35);bass(['C3','C3','G2','C3','D3','D3','A2','D3'][q],t,.12,.10);if(q===3||q===7)osc(note('C5'),t+b*.5,.085,.028,'sawtooth',0,2100);}
 else if(style==='break'){if([0,2,5].includes(q))drum('kick',t,.79);if(q===2||q===6)drum('snare',t,.9);drum('hat',t,.34);if(q%2===0)drum('hat',t+b*.5,.21);if(q===4)drum('snare',t+b*.7,.22);bass(['D3',null,'D3','F3','G3',null,'A2','C3'][q]||'D3',t,.15,.077);let mel=['D5',null,'F5','A5',null,'C6','A5',null][q];if(mel)osc(note(mel),t,.15,.032,'sawtooth',0,2200);}
 else if(style==='waltz'){if(s===0)drum('kick',t,.29);else drum('brush',t,.21);bass(['C3','G3','E3','F3','A3','C4'][i%6],t,.15,.039);let mel=['E5','G5','C6','B5','A5','G5','E5','D5','C5'][i%9];bell(mel,t,.38,.054);}
 else if(style==='ambient'){if(i%4===0)chord([['C4','G4','E5'],['A3','E4','C5'],['F3','C4','A4'],['G3','D4','B4']][Math.floor(k/4)],t,b*4,.020);if(i%2===0)bell(['G5','E5','A5','D5'][Math.floor(k/2)%4],t,b*1.8,.037);}
 else if(style==='soft'){if(s===0)drum('brush',t,.33);if(i%4===0)bass(['C3','A2','F2','G2'][Math.floor(k/4)],t,.28,.037);let mel=['G4','C5','E5','G5','E5','C5','A4','D5','F5','A5','F5','D5','G4','B4','D5','G5'][k];bell(mel,t,.27,.043);}
}
function cue(i,t,quiet=false){if($('music').value==='off')return;bell(i%2?'C6':'G5',t,.105,quiet?.075:.12);if($('music').value==='cues')drum('wood',t,.55);}
function resetSoundRound(){timeSettings();beatIndex=0;accentIndex=0;if(playing){initSound();resumeVolume();}}
function scheduleSound(){const style=$('music').value;if(isClassic(style)||style==='off')return;if(!audioCtx||audioCtx.state!=='running'||!playing||paused||finished)return;const ahead=.12,maxT=Math.min(roundLength,elapsed+ahead);
 while(beatIndex<beatsPerRound&&beatIndex*beatSeconds<=maxT){const at=beatIndex*beatSeconds;if(at>=elapsed-.06)playStyle(style,beatIndex,audioCtx.currentTime+Math.max(0,at-elapsed),beatSeconds);beatIndex++;}
 while(accentIndex<accents.length&&accents[accentIndex]*roundLength<=maxT){const at=accents[accentIndex]*roundLength;if(at>=elapsed-.06)cue(accentIndex,audioCtx.currentTime+Math.max(0,at-elapsed),style!=='cues');accentIndex++;}
}
function stopPreview(){if(previewInterval){clearInterval(previewInterval);previewInterval=0;}stopClassic();$('previewBtn').textContent='♫ Послушать стиль';if(!playing)silence();}
function startPreview(){if(playing){$('musicNote').textContent='Останови игру, чтобы отдельно прослушать.';return;}const v=$('music').value;if(v==='off')return;stopPreview();if(isClassic(v)){classicAudio=new Audio('assets/music/'+classicId(v)+'.mp3');classicAudio.volume=Number($('volume').value)/100;classicAudio.play().catch(()=>{});$('previewBtn').textContent='■ Остановить музыку';previewInterval=1;return;}if(!initSound())return;previewIndex=0;previewStart=audioCtx.currentTime+.06;const b=beatSeconds;previewInterval=setInterval(()=>{if(!audioCtx||audioCtx.state!=='running')return;const until=audioCtx.currentTime+.16,kind=$('music').value;while(previewStart+previewIndex*b<=until){const time=previewStart+previewIndex*b;if(kind==='cues')cue(previewIndex,time,false);else playStyle(kind,previewIndex,time,b);previewIndex++;if(previewIndex>999)previewIndex=0;}},35);resumeVolume();$('previewBtn').textContent='■ Остановить музыку';}
$('previewBtn').onclick=()=>{if(previewInterval)stopPreview();else startPreview();};
window.addEventListener('pagehide',()=>{stopPreview();silence();stopClassic();});
mode=$('mode').value;if(mode==='hemi'){$('shape').value='hemi';$('colorStyle').value='half';}timeSettings();computeLine();updateVisual(1);showOverlay('Линии в ритме','Розовый — левая рука, голубой — правая. Межполушарка: два зигзага подряд.','Начать игру');
})();
