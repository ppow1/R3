// R3 CONTROLLED SOURCE
// File: web/resident-avatar.js
// Component: R3-RESIDENT-AVATAR-WEB
// File Revision: 1.0.1
// Created: 2026-11-02T20:11:07.271Z
// Created By: ChatGPT GPT-6
// Purpose: Reusable, replaceable Three.js resident avatar client for the R3 website.
// Execution Model: Lazy browser module; loads a configured GLB and named animation clips.
// Observability: UI load/error state, asset identity/license, supported clips, and active clip.
// Dependencies: Three.js 0.180.0 via pinned jsDelivr import map; Gobkit OfficeLady GLB (CC0 1.0).
// Authority: R3 Charter Revision 2; no authentication or backend command bridge is implied.
// Changed: 2026-11-02T20:11:07.271Z | R3-AVATAR-001 | ChatGPT GPT-6 | Initial reusable browser avatar runtime.
// Changed: 2026-11-02T20:12:36.477Z | R3-AVATAR-002 | ChatGPT GPT-6 | Handle renderer import failures and correct mobile panel CSS.
// Supersedes: None
// Contracts: hints/resident-avatar-system.md; docs/IMPLEMENTATION_HANDOFF.md
// Tests: Not run; browser rendering and interaction acceptance pending.
// History/Predecessor: New file.
let THREE;
let GLTFLoader;

const asset = Object.freeze({
  id: 'gobkit-office-lady-v1',
  residentId: 'Grace',
  url: 'https://gobkit.com/freebies/human001/OfficeLady.glb',
  source: 'https://gobkit.itch.io/gobkit-free-character-pack-vol-1',
  license: 'CC0 1.0'
});
const residents = new Map();

const style = document.createElement('style');
style.textContent = [
  '#r3-avatar-launcher{font-size:12px}',
  '#r3-avatar-panel{position:fixed;z-index:42;right:24px;bottom:24px;width:min(330px,calc(100vw - 76px));height:min(470px,calc(100vh - 48px));display:grid;grid-template-rows:auto minmax(0,1fr) auto auto;overflow:hidden;color:#edf4fc;background:rgba(8,18,30,.88);border:1px solid #cde3ff66;border-radius:16px;backdrop-filter:blur(12px);box-shadow:0 18px 50px #0009}',
  '#r3-avatar-panel[hidden]{display:none}',
  '#r3-avatar-panel header{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid #c2d5ec33}',
  '#r3-avatar-panel header button{margin-left:auto;width:28px;height:28px;padding:0}',
  '#r3-avatar-stage{min-height:0;background:radial-gradient(ellipse at 50% 78%,#426f9955,transparent 62%),linear-gradient(#11223466,#050e17bb)}',
  '#r3-avatar-stage canvas{display:block;width:100%;height:100%}',
  '#r3-avatar-status{padding:7px 10px;font-size:10px;line-height:1.45;color:#c8d9ea;border-top:1px solid #c2d5ec22}',
  '#r3-avatar-status[data-state="error"]{color:#f1c4ba}',
  '#r3-avatar-actions{display:flex;gap:5px;flex-wrap:wrap;padding:8px 10px;border-top:1px solid #c2d5ec22}',
  '#r3-avatar-actions button{font-size:10px;padding:5px 8px}',
  '#r3-avatar-actions button[aria-pressed="true"]{background:#335879;border-color:#a9c6e6}',
  '@media(max-width:600px){#r3-avatar-panel{right:10px;bottom:10px;width:min(330px,calc(100vw - 70px));height:min(440px,calc(100vh - 20px))}}'
].join('');
document.head.append(style);

const nav = document.getElementById('side-rail');
if (nav) {
  const launcher = document.createElement('button');
  launcher.className = 'rail-button';
  launcher.id = 'r3-avatar-launcher';
  launcher.type = 'button';
  launcher.title = 'Grace temporary avatar';
  launcher.setAttribute('aria-label', 'Open Grace temporary avatar');
  launcher.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.5" r="3.4"></circle><path d="M5 21c.2-4.2 2.8-6.6 7-6.6s6.8 2.4 7 6.6"></path></svg><span class="rail-label">Grace</span>';
  const chat = document.getElementById('nav-chat');
  if (chat && chat.parentElement === nav) chat.after(launcher);
  else nav.append(launcher);

  const panel = document.createElement('section');
  panel.id = 'r3-avatar-panel';
  panel.hidden = true;
  panel.setAttribute('aria-label', 'Grace temporary avatar');
  panel.innerHTML = '<header><strong>Grace</strong><span style="font-size:10px;color:#c8d9ea">Temporary avatar</span><button type="button" id="r3-avatar-close" aria-label="Close avatar panel">×</button></header><div id="r3-avatar-stage" role="img" aria-label="Three-dimensional resident avatar"></div><div id="r3-avatar-status" aria-live="polite" data-state="loading">Avatar has not been loaded.</div><div id="r3-avatar-actions" aria-label="Avatar animation controls"></div>';
  document.body.append(panel);

  class ResidentAvatar {
    constructor(stage, status, controls) {
      this.stage = stage; this.statusNode = status; this.controls = controls;
      this.state = 'not-loaded'; this.names = []; this.current = null;
      this.visible = false; this.frame = 0; this.last = 0; this.loading = null;
    }
    status() {
      return Object.freeze({residentId: asset.residentId, state: this.state, assetId: asset.id,
        assetUrl: asset.url, license: asset.license, animations: [...this.names], currentAnimation: this.current});
    }
    report(message, state) {
      this.statusNode.textContent = message; this.statusNode.dataset.state = state;
    }
    async load() {
      if (this.mixer) return this.status();
      if (this.loading) return this.loading;
      this.state = 'loading'; this.report('Loading Three.js and temporary GLB avatar…', 'loading');
      try {
        if (!THREE || !GLTFLoader) {
          const modules = await Promise.all([import('three'), import('three/addons/loaders/GLTFLoader.js')]);
          THREE = modules[0];
          GLTFLoader = modules[1].GLTFLoader;
        }
      } catch (error) {
        this.state = 'error';
        this.report('Avatar renderer unavailable: Three.js dependency could not load.', 'error');
        throw error;
      }
      this.loading = new Promise((resolve, reject) => {
        const loader = new GLTFLoader();
        loader.setCrossOrigin('anonymous');
        loader.load(asset.url, (gltf) => {
          try {
            if (!gltf.scene || !gltf.animations?.length) throw new Error('GLB scene or named clips missing');
            this.gltf = gltf; this.scene = new THREE.Scene();
            this.camera = new THREE.PerspectiveCamera(32, 1, .01, 100);
            this.renderer = new THREE.WebGLRenderer({alpha:true, antialias:true, powerPreference:'low-power'});
            this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.5));
            this.renderer.outputColorSpace = THREE.SRGBColorSpace;
            this.renderer.setClearColor(0, 0);
            this.stage.replaceChildren(this.renderer.domElement);
            this.scene.add(new THREE.HemisphereLight(0xdceeff, 0x192535, 2.1));
            const light = new THREE.DirectionalLight(0xffedcf, 2.2); light.position.set(-2,4,4); this.scene.add(light);
            const model = gltf.scene;
            const box = new THREE.Box3().setFromObject(model);
            const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
            if (!Number.isFinite(size.y) || size.y <= 0) throw new Error('Character bounds unavailable');
            const scale = 1.65 / size.y; model.scale.setScalar(scale);
            model.position.set(-center.x*scale, -box.min.y*scale, -center.z*scale);
            this.scene.add(model); this.camera.position.set(0,1.05,3.7); this.camera.lookAt(0,.82,0);
            this.mixer = new THREE.AnimationMixer(model);
            this.actions = new Map(gltf.animations.map(clip => [clip.name,this.mixer.clipAction(clip)]));
            this.names = gltf.animations.map(clip => clip.name);
            const bounds = () => {
              const w=Math.max(1,this.stage.clientWidth), h=Math.max(1,this.stage.clientHeight);
              this.renderer.setSize(w,h,false); this.camera.aspect=w/h; this.camera.updateProjectionMatrix(); this.render();
            };
            this.observer = new ResizeObserver(bounds); this.observer.observe(this.stage); bounds();
            this.state = 'ready'; this.addControls();
            this.report('Temporary visual avatar loaded. Conversation and authorized resident control are not connected.', 'ready');
            this.play('Idle').catch(()=>{}); resolve(this.status());
          } catch (error) {
            this.state='error'; this.loading=null; this.report('Avatar unavailable: '+error.message,'error'); reject(error);
          }
        }, undefined, (error) => {
          this.state='error'; this.loading=null;
          this.report('Avatar unavailable: model or renderer dependency could not load.','error');
          reject(error instanceof Error ? error : new Error('Avatar dependency unavailable'));
        });
      });
      return this.loading;
    }
    addControls() {
      this.controls.replaceChildren();
      for (const name of ['Idle','Walk','Run','Special'].filter(n=>this.actions.has(n))) {
        const button=document.createElement('button'); button.type='button'; button.textContent=name;
        button.setAttribute('aria-pressed','false'); button.addEventListener('click',()=>this.play(name).catch(()=>{}));
        this.controls.append(button);
      }
    }
    async play(name, options={}) {
      if (!this.mixer) await this.load();
      const action=this.actions.get(name); if(!action) throw new Error('Animation not available: '+name);
      const loop=options.loop===undefined ? ['Idle','Walk','Run'].includes(name) : Boolean(options.loop);
      const fade=Number.isFinite(options.fadeSeconds)?Math.max(0,Math.min(2,options.fadeSeconds)):.22;
      const previous=this.active; action.reset(); action.setLoop(loop?THREE.LoopRepeat:THREE.LoopOnce,loop?Infinity:1);
      action.clampWhenFinished=!loop; action.play();
      if(previous&&previous!==action&&fade) previous.crossFadeTo(action,fade,false);
      this.active=action; this.current=name;
      for(const b of this.controls.querySelectorAll('button')) b.setAttribute('aria-pressed',String(b.textContent===name));
      if(this.visible)this.start();
      return this.status();
    }
    render() { if(this.renderer&&this.scene&&this.camera)this.renderer.render(this.scene,this.camera); }
    start() {
      if(this.frame||!this.renderer)return;
      const tick=(t)=>{if(!this.visible){this.frame=0;return;}const d=this.last?Math.min((t-this.last)/1000,.05):0;this.last=t;this.mixer?.update(d);this.render();this.frame=requestAnimationFrame(tick);};
      this.frame=requestAnimationFrame(tick);
    }
    setVisible(value) {
      this.visible=Boolean(value);
      if(this.visible)this.start();
      else {cancelAnimationFrame(this.frame);this.frame=0;this.last=0;}
    }
    dispose() {
      this.setVisible(false); this.observer?.disconnect(); this.mixer?.stopAllAction();
      this.gltf?.scene.traverse(n=>{n.geometry?.dispose();if(Array.isArray(n.material))n.material.forEach(m=>m.dispose());else n.material?.dispose();});
      this.renderer?.dispose(); this.state='disposed';
    }
  }

  const avatar = new ResidentAvatar(document.getElementById('r3-avatar-stage'),
    document.getElementById('r3-avatar-status'), document.getElementById('r3-avatar-actions'));
  residents.set('Grace', Object.freeze({avatar}));
  launcher.addEventListener('click', async () => {
    panel.hidden=!panel.hidden; avatar.setVisible(!panel.hidden);
    if(!panel.hidden) try { await avatar.load(); } catch (_) {}
  });
  document.getElementById('r3-avatar-close').addEventListener('click',()=>{panel.hidden=true;avatar.setVisible(false);});
  window.addEventListener('beforeunload',()=>avatar.dispose(),{once:true});
}

window.r3Residents = Object.freeze({
  get(id) { return residents.get(id); },
  list() { return Array.from(residents.keys()); },
  command(command) {
    if(!command||command.type!=='play-animation'||typeof command.residentId!=='string'||typeof command.animation!=='string')
      return Promise.reject(new TypeError('Expected type, residentId, and animation'));
    const resident=residents.get(command.residentId);
    if(!resident)return Promise.reject(new Error('Resident avatar unavailable: '+command.residentId));
    return resident.avatar.play(command.animation,{loop:command.loop,fadeSeconds:command.fadeSeconds});
  }
});
window.dispatchEvent(new CustomEvent('r3:resident-avatar-ready',{detail:{residentId:asset.residentId}}));
