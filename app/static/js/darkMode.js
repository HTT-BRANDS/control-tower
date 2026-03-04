// Dark Mode Toggle (P5: cje)
(function(){
  const key='theme-preference';
  function getTheme(){return localStorage.getItem(key)||'system';}
  function apply(t){
    const d=document.documentElement;
    if(t==='system'){d.removeAttribute('data-theme');const m=window.matchMedia('(prefers-color-scheme:dark)');d.setAttribute('data-theme',m.matches?'dark':'light');}
    else{d.setAttribute('data-theme',t);}
    localStorage.setItem(key,t);
  }
  apply(getTheme());
  window.matchMedia('(prefers-color-scheme:dark)').addEventListener('change',function(){if(getTheme()==='system')apply('system');});
  window.toggleTheme=function(){const c=document.documentElement.getAttribute('data-theme');apply(c==='dark'?'light':'dark');};
})();
