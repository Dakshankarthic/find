const $ = id => document.getElementById(id);
let busy = false;
async function api(path, options = {}) {
  const response = await fetch(path, {cache:'no-store', ...options});
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.detail || 'Something went wrong. Please try again.'), {status:response.status});
  return data;
}
function showTracker(name) {
  $('tracker-name').textContent = name;
  $('login-view').hidden = true;
  $('tracker-view').hidden = false;
}
function clearLocation() {
  $('map').hidden = true; $('map').removeAttribute('src'); $('map-empty').hidden = false;
  $('maps-link').removeAttribute('href'); $('maps-link').classList.add('disabled'); $('maps-link').setAttribute('aria-disabled','true');
  $('coordinates').textContent = '—'; $('last-seen').textContent = 'Waiting for a report'; $('accuracy').textContent = '—';
  $('status').textContent = 'Ready to locate'; $('status-dot').classList.remove('found');
}
function present(data) {
  $('tracker-name').textContent = data.name;
  if (!data.location) {
    clearLocation(); $('status').textContent = 'No location report yet';
    $('map-title').textContent = 'No report just yet';
    $('map-message').textContent = 'Keep your tracker powered. A nearby Android device needs to detect it before a location can appear.';
    return;
  }
  const p = data.location;
  if (![p.latitude,p.longitude,p.timestamp].every(Number.isFinite) || Math.abs(p.latitude)>90 || Math.abs(p.longitude)>180) throw new Error('The location report was invalid. Please refresh again.');
  const coords = `${p.latitude.toFixed(6)}, ${p.longitude.toFixed(6)}`;
  const query = `${p.latitude},${p.longitude}`;
  $('last-seen').textContent = new Date(p.timestamp*1000).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'});
  $('coordinates').textContent = coords;
  $('accuracy').textContent = p.accuracy>0 ? `About ${Math.round(p.accuracy)} m` : 'Not provided';
  $('status').textContent = 'Location report received'; $('status-dot').classList.add('found');
  $('maps-link').href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
  $('maps-link').classList.remove('disabled'); $('maps-link').removeAttribute('aria-disabled');
  $('map').src = `https://maps.google.com/maps?q=${encodeURIComponent(query)}&z=16&output=embed`;
  $('map').hidden = false; $('map-empty').hidden = true;
  $('map-note').textContent = 'Latest reported position';
}
async function refresh() {
  if (busy) return;
  busy = true; $('refresh').disabled=true; $('tracker-view').classList.add('loading');
  $('refresh-label').textContent = 'Finding your tracker…'; $('request-error').textContent='';
  try { present(await api('/api/refresh',{method:'POST'})); }
  catch(error) {
    if(error.status===401){clearLocation(); $('tracker-view').hidden=true; $('login-view').hidden=false;}
    $('request-error').textContent=error.message;
  } finally {busy=false; $('refresh').disabled=false; $('tracker-view').classList.remove('loading'); $('refresh-label').textContent='Refresh location';}
}
$('login-form').addEventListener('submit',async event=>{
  event.preventDefault(); $('sign-in').disabled=true; $('login-error').textContent='';
  try {await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('password').value})}); $('password').value=''; const state=await api('/api/session');showTracker(state.name); await refresh();}
  catch(error){$('login-error').textContent=error.message;}
  finally{$('sign-in').disabled=false;}
});
$('refresh').addEventListener('click',refresh);
$('logout').addEventListener('click',async()=>{try{await api('/api/logout',{method:'POST'});clearLocation();$('tracker-view').hidden=true;$('login-view').hidden=false;}catch(error){$('request-error').textContent=error.message;}});
api('/api/session').then(state=>{if(state.authenticated){showTracker(state.name);refresh();}else if(!state.configured){$('login-error').textContent='Setup needed: add your private environment variables in Vercel, then redeploy.';}}).catch(()=>{$('login-error').textContent='Unable to reach the server. Please reload.';});
