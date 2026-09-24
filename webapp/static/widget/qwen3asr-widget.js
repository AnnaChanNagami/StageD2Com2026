/*
 * Qwen3-ASR Widget — bouton de transcription vocale embarquable.
 *
 * Usage sur n'importe quel site :
 *   <script>
 *     window.QWEN3ASR_WIDGET = { apiBase: "https://votre-serveur-asr" };
 *   </script>
 *   <script src="https://votre-serveur-asr/static/widget/qwen3asr-widget.js"></script>
 *
 * Si le script est hébergé par le serveur ASR lui-même, apiBase est déduit
 * automatiquement de l'origine du script (aucune config requise).
 *
 * Options (window.QWEN3ASR_WIDGET) :
 *   apiBase   : origine du serveur Django (ex "http://127.0.0.1:8003")
 *   position  : "bottom-right" (défaut) | "bottom-left" | "top-right" | "top-left"
 *   accent    : couleur principale (défaut "#3a6fd8")
 *   title     : titre du panneau (défaut "Transcription vocale")
 *   lang      : langue forcée pour l'ASR ("" = auto)
 *   timestamps: true pour activer timestamps/segments (SRT)
 *   maxTokens : limite de tokens générés
 */
(function () {
  'use strict';

  var CONFIG = window.QWEN3ASR_WIDGET || {};
  var API_BASE = String(CONFIG.apiBase || '').replace(/\/+$/, '');
  var SCRIPT_PATTERN = 'qwen3asr-widget';
  var POSITION = ['bottom-right', 'bottom-left', 'top-right', 'top-left'].indexOf(CONFIG.position) >= 0 ? CONFIG.position : 'bottom-right';
  var ACCENT = CONFIG.accent || '#3a6fd8';
  var TITLE = CONFIG.title || 'Transcription vocale';

  /* ------------------------------------------------------------------ *
   * API_BASE : déduction automatique depuis l'origine du script
   * ------------------------------------------------------------------ */
  if (!API_BASE) {
    var scripts = document.querySelectorAll('script[src*="' + SCRIPT_PATTERN + '"]');
    if (scripts.length) {
      var a = document.createElement('a');
      a.href = scripts[scripts.length - 1].src;
      API_BASE = a.origin;
    }
  }

  /* ------------------------------------------------------------------ *
   * CSS encapsulé (préfixe qw3-)
   * ------------------------------------------------------------------ */
  var CSS =
    '.qw3-widget{position:fixed;z-index:2147483000;font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;' +
    'line-height:1.45;}' +
    '.qw3-widget *,.qw3-widget *::before,.qw3-widget *::after{box-sizing:border-box;margin:0;padding:0;}' +
    '.qw3-fab{width:60px;height:60px;border-radius:50%;border:none;cursor:pointer;display:grid;place-items:center;' +
    'background:linear-gradient(135deg,' + ACCENT + ',#1f3864);color:#fff;box-shadow:0 10px 28px rgba(10,20,36,.45);' +
    'transition:transform .15s ease,box-shadow .15s ease;}' +
    '.qw3-fab:hover{transform:scale(1.06);box-shadow:0 14px 32px rgba(10,20,36,.55);}' +
    '.qw3-fab:active{transform:scale(.97);}' +
    '.qw3-fab.qw3-rec{background:linear-gradient(135deg,#e11d48,#9f1239);animation:qw3-pulse 1.4s ease-in-out infinite;}' +
    '.qw3-fab.qw3-busy{background:linear-gradient(135deg,#334155,#0f172a);cursor:progress;}' +
    '.qw3-fab svg{width:26px;height:26px;}' +
    '.qw3-panel{position:absolute;width:340px;max-width:calc(100vw - 24px);max-height:min(60vh,520px);' +
    'display:flex;flex-direction:column;overflow:hidden;border-radius:16px;' +
    'background:rgba(13,27,51,.96);color:#e2e8f0;border:1px solid rgba(90,140,240,.35);' +
    'box-shadow:0 24px 60px rgba(0,0,0,.5);backdrop-filter:blur(10px);}' +
    '.qw3-panel[hidden]{display:none;}' +
    '.qw3-panel-head{display:flex;align-items:center;gap:10px;padding:14px 16px;' +
    'border-bottom:1px solid rgba(255,255,255,.08);}' +
    '.qw3-panel-head .qw3-logo{width:34px;height:34px;flex:none;border-radius:10px;display:grid;place-items:center;' +
    'background:linear-gradient(135deg,' + ACCENT + ',#1f3864);color:#fff;}' +
    '.qw3-panel-head .qw3-logo svg{width:17px;height:17px;}' +
    '.qw3-panel-title{font-size:14px;font-weight:700;color:#f1f5f9;}' +
    '.qw3-panel-sub{font-size:11px;color:#94a3b8;}' +
    '.qw3-close{margin-left:auto;width:28px;height:28px;border:none;border-radius:8px;cursor:pointer;' +
    'background:rgba(255,255,255,.06);color:#cbd5e1;display:grid;place-items:center;}' +
    '.qw3-close:hover{background:rgba(255,255,255,.14);}' +
    '.qw3-close svg{width:14px;height:14px;}' +
    '.qw3-body{overflow-y:auto;padding:14px 16px;flex:1;font-size:13.5px;}' +
    '.qw3-status{display:flex;align-items:center;gap:8px;font-size:13px;color:#cbd5e1;}' +
    '.qw3-dot{width:8px;height:8px;border-radius:50%;background:#e11d48;flex:none;animation:qw3-blink 1s infinite;}' +
    '.qw3-bar{height:6px;border-radius:4px;background:rgba(255,255,255,.1);margin-top:10px;overflow:hidden;}' +
    '.qw3-bar i{display:block;height:100%;border-radius:4px;background:linear-gradient(90deg,' + ACCENT + ',#8ab4ff);' +
    'transition:width .6s ease;}' +
    '.qw3-hint{font-size:11.5px;color:#7c8aa5;margin-top:10px;}' +
    '.qw3-transcript{white-space:pre-wrap;word-break:break-word;color:#e2e8f0;font-size:13.5px;}' +
    '.qw3-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;}' +
    '.qw3-chip{font-size:10.5px;padding:3px 8px;border-radius:999px;background:rgba(90,140,240,.16);' +
    'color:#8ab4ff;border:1px solid rgba(90,140,240,.28);}' +
    '.qw3-error{color:#fda4af;background:rgba(225,29,72,.12);border:1px solid rgba(225,29,72,.3);' +
    'border-radius:10px;padding:10px 12px;font-size:12.5px;}' +
    '.qw3-foot{display:flex;gap:8px;padding:12px 16px;border-top:1px solid rgba(255,255,255,.08);flex-wrap:wrap;}' +
    '.qw3-btn{display:inline-flex;align-items:center;gap:6px;border:none;cursor:pointer;border-radius:10px;' +
    'padding:8px 12px;font-size:12.5px;font-weight:600;color:#e2e8f0;background:rgba(255,255,255,.07);' +
    'transition:background .12s ease;}' +
    '.qw3-btn:hover{background:rgba(255,255,255,.14);}' +
    '.qw3-btn svg{width:14px;height:14px;}' +
    '.qw3-btn.qw3-primary{background:linear-gradient(135deg,' + ACCENT + ',#1f3864);color:#fff;}' +
    '.qw3-btn.qw3-primary:hover{filter:brightness(1.12);}' +
    '.qw3-btn.qw3-danger{color:#fda4af;}' +
    '.qw3-btn[disabled]{opacity:.5;cursor:not-allowed;}' +
    '.qw3-file{display:none;}' +
    '.qw3-toast{position:fixed;z-index:2147483001;left:50%;bottom:90px;transform:translateX(-50%);' +
    'max-width:min(420px,calc(100vw - 32px));background:rgba(13,27,51,.97);color:#e2e8f0;' +
    'border:1px solid rgba(90,140,240,.4);border-radius:12px;padding:10px 16px;font-size:13px;' +
    'box-shadow:0 12px 40px rgba(0,0,0,.5);' + (POSITION.indexOf('top') === 0 ? 'top:90px;bottom:auto;' : '') + '}' +
    '.qw3-spin{animation:qw3-spin .9s linear infinite;}' +
    '@keyframes qw3-spin{to{transform:rotate(360deg);}}' +
    '@keyframes qw3-pulse{0%,100%{box-shadow:0 0 0 0 rgba(225,29,72,.5);}50%{box-shadow:0 0 0 14px rgba(225,29,72,0);}}' +
    '@keyframes qw3-blink{50%{opacity:.35;}}';

  var styleEl = document.createElement('style');
  styleEl.textContent = CSS;
  (document.head || document.documentElement).appendChild(styleEl);

  /* ------------------------------------------------------------------ *
   * Icônes SVG
   * ------------------------------------------------------------------ */
  var SVGS = {
    mic: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5.5-3a5.5 5.5 0 0 1-11 0H4a8 8 0 0 0 7 7.93V22h2v-3.07A8 8 0 0 0 20 11h-2.5z"/></svg>',
    stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
    spin: '<svg class="qw3-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M12 2a10 10 0 0 1 10 10"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 13l5 5L20 6"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 7v6"/><circle cx="12" cy="17" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="9"/></svg>',
    file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v4h4"/></svg>',
    folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v4h-4"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>'
  };

  /* ------------------------------------------------------------------ *
   * DOM
   * ------------------------------------------------------------------ */
  var root = document.createElement('div');
  root.className = 'qw3-widget';
  root.style.bottom = POSITION.indexOf('bottom') === 0 ? '24px' : 'auto';
  root.style.top = POSITION.indexOf('top') === 0 ? '24px' : 'auto';
  root.style.left = POSITION.indexOf('left') >= 0 ? '24px' : 'auto';
  root.style.right = POSITION.indexOf('right') >= 0 ? '24px' : 'auto';

  var panel = document.createElement('div');
  panel.className = 'qw3-panel';
  panel.hidden = true;
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', TITLE);

  panel.innerHTML =
    '<div class="qw3-panel-head">' +
      '<span class="qw3-logo">' + SVGS.mic + '</span>' +
      '<div><div class="qw3-panel-title"></div><div class="qw3-panel-sub">Qwen3-ASR</div></div>' +
      '<button type="button" class="qw3-close" aria-label="Fermer">' + SVGS.close + '</button>' +
    '</div>' +
    '<div class="qw3-body"></div>' +
    '<div class="qw3-foot">' +
      '<button type="button" class="qw3-btn qw3-primary qw3-act-record">' + SVGS.mic + '<span></span></button>' +
      '<button type="button" class="qw3-btn qw3-act-file">' + SVGS.folder + '<span>Fichier</span></button>' +
      '<button type="button" class="qw3-btn qw3-act-copy" hidden>' + SVGS.copy + '<span>Copier</span></button>' +
      '<button type="button" class="qw3-btn qw3-danger qw3-act-reset" hidden>' + SVGS.refresh + '<span>Effacer</span></button>' +
    '</div>';

  var fab = document.createElement('button');
  fab.type = 'button';
  fab.className = 'qw3-fab';
  fab.setAttribute('aria-label', 'Transcription vocale');
  fab.title = TITLE;
  fab.innerHTML = SVGS.mic;

  var fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.className = 'qw3-file';
  fileInput.accept = '.wav,.mp3,.mp4,.flac,.m4a,.ogg,.opus,.aac,.wma,.mov,.mkv,.webm,.amr,audio/*';

  root.appendChild(panel);
  root.appendChild(fab);
  root.appendChild(fileInput);
  (document.body || document.documentElement).appendChild(root);

  /* ------------------------------------------------------------------ *
   * État
   * ------------------------------------------------------------------ */
  var state = 'idle'; // idle | recording | processing | done | error
  var recorder = null;
  var mediaStream = null;
  var chunks = [];
  var jobId = null;
  var pollTimer = null;

  var titleEl = root.querySelector('.qw3-panel-title');
  var bodyEl = root.querySelector('.qw3-body');
  var closeBtn = root.querySelector('.qw3-close');
  var btnRec = root.querySelector('.qw3-act-record');
  var btnFile = root.querySelector('.qw3-act-file');
  var btnCopy = root.querySelector('.qw3-act-copy');
  var btnReset = root.querySelector('.qw3-act-reset');
  var lastTranscript = '';

  titleEl.textContent = TITLE;

  /* ------------------------------------------------------------------ *
   * Utilitaires
   * ------------------------------------------------------------------ */
  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function fmtSize(b) {
    if (b >= 1048576) return (b / 1048576).toFixed(1).replace('.', ',') + ' Mo';
    if (b >= 1024) return Math.round(b / 1024) + ' Ko';
    return b + ' o';
  }

  var toastEl = null;
  function toast(msg, ms) {
    if (toastEl) toastEl.remove();
    toastEl = document.createElement('div');
    toastEl.className = 'qw3-toast';
    toastEl.textContent = msg;
    (document.body || document.documentElement).appendChild(toastEl);
    setTimeout(function () { if (toastEl) { toastEl.remove(); toastEl = null; } }, ms || 3000);
  }

  /* ------------------------------------------------------------------ *
   * Rendu des états
   * ------------------------------------------------------------------ */
  function setFab(icon, cls, label) {
    fab.innerHTML = SVGS[icon];
    fab.className = 'qw3-fab' + (cls ? ' ' + cls : '');
    fab.setAttribute('aria-label', label);
  }

  function render() {
    if (state === 'idle') {
      setFab('mic', '', 'Enregistrer la voix');
      bodyEl.innerHTML =
        '<div class="qw3-status"><span class="qw3-dot"></span> Prêt — cliquez pour enregistrer</div>' +
        '<div class="qw3-hint">Cliquez sur le bouton micro ci-dessous, ou déposez un fichier audio sur le bouton rond.</div>';
      btnRec.hidden = false;
      btnRec.querySelector('span').textContent = 'Enregistrer';
      btnRec.innerHTML = SVGS.mic + '<span>Enregistrer</span>';
      btnFile.hidden = false;
      btnCopy.hidden = true;
      btnReset.hidden = true;
    } else if (state === 'recording') {
      setFab('stop', 'qw3-rec', "Arrêter l'enregistrement");
      bodyEl.innerHTML =
        '<div class="qw3-status"><span class="qw3-dot"></span> Enregistrement en cours…</div>' +
        '<div class="qw3-hint">Cliquez à nouveau sur le bouton pour arrêter et lancer la transcription.</div>';
      btnRec.hidden = false;
      btnRec.innerHTML = SVGS.stop + '<span>Arrêter</span>';
      btnFile.hidden = true;
      btnCopy.hidden = true;
      btnReset.hidden = false;
    } else if (state === 'processing') {
      setFab('spin', 'qw3-busy', 'Transcription en cours');
      bodyEl.innerHTML =
        '<div class="qw3-status">' + SVGS.spin + ' <span>Transcription en cours…</span></div>' +
        '<div class="qw3-bar"><i id="qw3bar" style="width:8%"></i></div>' +
        '<div class="qw3-hint" id="qw3stage">Upload du fichier…</div>';
      btnRec.hidden = true;
      btnFile.hidden = true;
      btnCopy.hidden = true;
      btnReset.hidden = true;
    } else if (state === 'done') {
      setFab('check', '', 'Transcription terminée');
      var meta = '';
      if (jobMeta) {
        var bits = [];
        if (jobMeta.language) bits.push('Langue : ' + esc(jobMeta.language));
        if (jobMeta.words) bits.push(esc(jobMeta.words) + ' mots');
        if (jobMeta.elapsed) bits.push('Analyse : ' + esc(jobMeta.elapsed) + ' s');
        if (bits.length) meta = '<div class="qw3-meta">' + bits.map(function (b) { return '<span class="qw3-chip">' + b + '</span>'; }).join('') + '</div>';
      }
      bodyEl.innerHTML =
        '<div class="qw3-status" style="color:#4ade80"><span style="width:8px;height:8px;border-radius:50%;background:#4ade80;display:inline-block;flex:none"></span> Transcription terminée</div>' +
        '<div class="qw3-transcript" style="margin-top:10px">' + esc(lastTranscript || '—') + '</div>' + meta;
      btnRec.hidden = false;
      btnRec.innerHTML = SVGS.mic + '<span>Nouvelle</span>';
      btnFile.hidden = false;
      btnCopy.hidden = !lastTranscript;
      btnReset.hidden = false;
    } else if (state === 'error') {
      setFab('alert', '', 'Réessayer');
      bodyEl.innerHTML =
        '<div class="qw3-error">' + SVGS.alert + '<div style="margin-top:6px">' + esc(lastError || 'Une erreur est survenue.') + '</div></div>';
      btnRec.hidden = false;
      btnRec.innerHTML = SVGS.mic + '<span>Réessayer</span>';
      btnFile.hidden = false;
      btnCopy.hidden = true;
      btnReset.hidden = false;
    }
  }

  var lastError = '';
  var jobMeta = null;

  function setState(s) {
    state = s;
    render();
  }

  function setProgress(pct, stage) {
    var bar = bodyEl.querySelector('#qw3bar');
    var st = bodyEl.querySelector('#qw3stage');
    if (bar) bar.style.width = Math.max(8, Math.min(100, pct)) + '%';
    if (st) st.textContent = stage || 'Transcription en cours…';
  }

  function openPanel() {
    panel.hidden = false;
    render();
  }

  function closePanel() {
    panel.hidden = true;
  }

  /* ------------------------------------------------------------------ *
   * Enregistrement micro
   * ------------------------------------------------------------------ */
  function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError('Enregistrement micro non supporté par ce navigateur. Utilisez un fichier audio.');
      return;
    }
    if (!window.MediaRecorder) {
      setError('MediaRecorder non disponible dans ce navigateur. Utilisez un fichier audio.');
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      mediaStream = stream;
      chunks = [];
      var mime = (window.MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : null) ||
                 (window.MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '');
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorder.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      recorder.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        var type = (recorder.mimeType || 'audio/webm').split(';')[0];
        var ext = type === 'audio/mp4' ? 'm4a' : 'webm';
        var blob = new Blob(chunks, { type: type });
        var file = new File([blob], 'enregistrement.' + ext, { type: type });
        upload(file);
      };
      recorder.onerror = function () { stopRecording(); setError('Erreur de l\'enregistrement audio.'); };
      recorder.start(250);
      setState('recording');
    }).catch(function (err) {
      var msg = 'Impossible d\'accéder au micro.';
      if (err && err.name === 'NotAllowedError') msg = 'Accès au micro refusé. Autorisez le micro dans le navigateur, ou utilisez un fichier audio.';
      else if (err && err.name === 'NotFoundError') msg = 'Aucun micro détecté. Utilisez un fichier audio à la place.';
      else if (err && err.name === 'NotReadableError') msg = 'Le micro est utilisé par une autre application.';
      setError(msg);
    });
  }

  function stopRecording() {
    if (recorder && recorder.state !== 'inactive') {
      try { recorder.stop(); } catch (e) { /* déjà arrêté */ }
    } else if (mediaStream) {
      mediaStream.getTracks().forEach(function (t) { t.stop(); });
    }
  }

  /* ------------------------------------------------------------------ *
   * Upload + polling
   * ------------------------------------------------------------------ */
  function upload(file) {
    if (!API_BASE) {
      setError('API non configurée : renseignez window.QWEN3ASR_WIDGET.apiBase (origine du serveur ASR).');
      return;
    }
    setState('processing');
    setProgress(5, 'Upload du fichier…');

    var fd = new FormData();
    fd.append('audio_file', file, file.name);
    if (CONFIG.lang) fd.append('language', CONFIG.lang);
    if (CONFIG.timestamps) fd.append('timestamps', '1');
    if (CONFIG.maxTokens) fd.append('max_new_tokens', CONFIG.maxTokens);

    fetch(API_BASE + '/jobs/create/', { method: 'POST', body: fd })
      .then(function (resp) {
        return resp.json().then(function (data) {
          if (!resp.ok) throw new Error(data.error || ('Erreur serveur (' + resp.status + ')'));
          return data;
        });
      })
      .then(function (data) {
        jobId = data.id;
        setProgress(12, 'En attente du moteur…');
        pollStatus(jobId);
      })
      .catch(function (err) {
        setError(err && err.message ? err.message : 'Échec de l\'envoi du fichier.');
      });
  }

  function pollStatus(id, attempt) {
    attempt = attempt || 0;
    clearTimeout(pollTimer);
    fetch(API_BASE + '/api/status/' + id + '/')
      .then(function (resp) {
        if (!resp.ok) throw new Error('Le serveur n\'a pas répondu (' + resp.status + ').');
        return resp.json();
      })
      .then(function (data) {
        if (data.status === 'completed') {
          lastTranscript = data.transcript_text || '';
          jobMeta = {
            language: data.language_detected || '',
            words: lastTranscript.trim() ? lastTranscript.trim().split(/\s+/).length : 0,
            elapsed: data.elapsed_sec ? Math.round(data.elapsed_sec) : null
          };
          setProgress(100, 'Terminé');
          setState('done');
        } else if (data.status === 'failed') {
          setError(data.error || 'La transcription a échoué côté serveur.');
        } else {
          var pct = 12 + Math.round(((data.progress || 0) / 100) * 70);
          setProgress(pct, 'Transcription en cours… (' + pct + ' %)');
          pollTimer = setTimeout(function () { pollStatus(id, attempt + 1); }, 2000);
        }
      })
      .catch(function (err) {
        if (attempt < 5) {
          pollTimer = setTimeout(function () { pollStatus(id, attempt + 1); }, 2500);
        } else {
          setError(err && err.message ? err.message : 'Impossible de suivre la transcription.');
        }
      });
  }

  /* ------------------------------------------------------------------ *
   * Erreurs / reset
   * ------------------------------------------------------------------ */
  function setError(msg) {
    lastError = msg;
    clearTimeout(pollTimer);
    setState('error');
    toast(msg, 4000);
  }

  function resetAll() {
    clearTimeout(pollTimer);
    if (recorder && recorder.state !== 'inactive') { try { recorder.stop(); } catch (e) {} }
    if (mediaStream) mediaStream.getTracks().forEach(function (t) { t.stop(); });
    recorder = null; mediaStream = null; chunks = []; jobId = null; jobMeta = null;
    lastTranscript = ''; lastError = '';
    setState('idle');
  }

  /* ------------------------------------------------------------------ *
   * Copy
   * ------------------------------------------------------------------ */
  function copyTranscript() {
    if (!lastTranscript) return;
    var done = function () { toast('Texte copié dans le presse-papiers.'); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(lastTranscript).then(done).catch(function () { fallbackCopy(); });
    } else fallbackCopy();
    function fallbackCopy() {
      var ta = document.createElement('textarea');
      ta.value = lastTranscript;
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); done(); } catch (e) { toast('Copie impossible — sélectionnez le texte manuellement.'); }
      ta.remove();
    }
  }

  /* ------------------------------------------------------------------ *
   * Événements
   * ------------------------------------------------------------------ */
  fab.addEventListener('click', function () {
    if (state === 'recording') {
      stopRecording();
    } else if (state === 'processing') {
      toast('Transcription en cours, patientez…');
    } else if (state === 'done' || state === 'error') {
      openPanel();
    } else {
      openPanel();
      if (panel.hidden) return;
      startRecording();
    }
  });

  fab.addEventListener('dragover', function (e) {
    e.preventDefault();
    e.stopPropagation();
    fab.style.outline = '2px dashed ' + ACCENT;
  });
  fab.addEventListener('dragleave', function () { fab.style.outline = ''; });
  fab.addEventListener('drop', function (e) {
    e.preventDefault();
    e.stopPropagation();
    fab.style.outline = '';
    var files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) handleFile(files[0]);
    else toast('Déposez un fichier audio.');
  });

  closeBtn.addEventListener('click', closePanel);

  btnRec.addEventListener('click', function () {
    if (state === 'recording') stopRecording();
    else if (state === 'processing') toast('Transcription en cours, patientez…');
    else if (state === 'done' || state === 'error') resetAll();
    else startRecording();
  });

  btnFile.addEventListener('click', function () { fileInput.click(); });
  fileInput.addEventListener('change', function () {
    if (fileInput.files && fileInput.files.length) handleFile(fileInput.files[0]);
    fileInput.value = '';
  });

  btnCopy.addEventListener('click', copyTranscript);
  btnReset.addEventListener('click', resetAll);

  function handleFile(file) {
    if (!file) return;
    var ok = /\.(wav|mp3|mp4|flac|m4a|ogg|opus|aac|wma|mov|mkv|webm|amr)$/i.test(file.name) || (file.type && file.type.indexOf('audio/') === 0);
    if (!ok) {
      setError('Format non pris en charge : ' + esc(file.name));
      return;
    }
    if (state === 'recording') stopRecording();
    setState('processing');
    setProgress(4, 'Envoi de ' + esc(file.name) + ' (' + fmtSize(file.size) + ')…');
    upload(file);
  }

  /* ------------------------------------------------------------------ *
   * Démarrage
   * ------------------------------------------------------------------ */
  function boot() {
    if (window.Qwen3ASRWidget) return;
    window.Qwen3ASRWidget = {
      transcribe: function (file) { handleFile(file); return window.Qwen3ASRWidget; },
      reset: function () { resetAll(); },
      open: function () { openPanel(); },
      close: function () { closePanel(); }
    };
    if (!API_BASE) {
      console.warn('[Qwen3-ASR Widget] apiBase non détecté — renseignez window.QWEN3ASR_WIDGET.apiBase.');
    }
  }

  if (document.body) boot();
  else document.addEventListener('DOMContentLoaded', boot);
})();