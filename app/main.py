from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api import public, admin
from app.core.config import Settings
from app.core.logging import setup_logging
from app.db.session import init_db

setup_logging(Settings().log_level)

app = FastAPI(title="Open DART Fund Quiz Service", version="0.1.0")

_origins_raw = Settings().cors_allow_origins or "*"
if _origins_raw.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


HTML_LANDING = """<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Fund Quiz</title>
    <style>
      :root {
        --bg: #f5f7fb;
        --panel: #ffffff;
        --line: #dde3ec;
        --text: #202633;
        --muted: #5c6779;
        --primary: #2563eb;
        --primary-weak: #dbeafe;
        --ok: #118c4f;
        --danger: #b42318;
      }
      * { box-sizing: border-box; }
      body {
        font-family: Inter, Pretendard, 'Apple SD Gothic Neo', 'Malgun Gothic', Arial, sans-serif;
        margin: 0;
        padding: 24px;
        background: linear-gradient(180deg, #f9fbff 0%, #f5f7fb 45%, #eef2f8 100%);
        color: var(--text);
      }
      .wrap { max-width: 1024px; margin: 0 auto; }
      h1 { font-size: 1.7rem; margin: 0 0 14px; letter-spacing: -0.02em; }
      .subtitle { color: var(--muted); margin: 0 0 20px; }
      .card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
      }
      .card h2, .card h3 { margin: 0 0 12px; }
      .row { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0; align-items: center; }
      .btn, .small-btn {
        border: 0;
        border-radius: 10px;
        padding: 7px 10px;
        cursor: pointer;
        font-weight: 600;
        font-size: 12px;
        line-height: 1.15;
        transition: transform .12s ease, box-shadow .12s ease;
      }
      .btn { background: var(--primary); color: #fff; }
      .btn:hover { box-shadow: 0 6px 16px rgba(37,99,235,.22); transform: translateY(-1px); }
      .small-btn { background: #f1f5ff; color: #133f9c; }
      .small-btn:hover { background: #dbeafe; }
      .compact-btn {
        padding: 5px 8px !important;
        font-size: 11px !important;
        border-radius: 8px;
      }
      .btn:disabled { opacity: .6; cursor: not-allowed; }
      input, select {
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 10px 12px;
        min-width: 220px;
        font-size: 14px;
        background: #fff;
      }
      input:focus, select:focus { outline: none; border-color: #9cb7ff; box-shadow: 0 0 0 4px rgba(37,99,235,.12); }
      .question {
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 14px;
        margin: 12px 0;
        background: #fbfdff;
      }
      .question + .question {
        margin-top: 14px;
      }
      .quiz-info {
        background: #f8faff;
        border: 1px solid #e2ebff;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
      }
      .quiz-meta {
        display: grid;
        gap: 2px;
        color: var(--muted);
        font-size: 13px;
      }
      .choices {
        display: grid;
        gap: 4px;
      }
      .question-footer {
        margin-top: 8px;
        color: var(--muted);
        font-size: 12px;
      }
      .difficulty-chip {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 3px 9px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .01em;
        border: 1px solid transparent;
      }
      .difficulty-chip.easy {
        background: #ecfdf3;
        color: #0f7a45;
        border-color: #b7ebcc;
      }
      .difficulty-chip.medium {
        background: #fff7e8;
        color: #9a5b00;
        border-color: #ffd79a;
      }
      .difficulty-chip.hard {
        background: #fff0f1;
        color: #b42318;
        border-color: #ffc2c7;
      }
      .difficulty-chip.unknown {
        background: #eef2ff;
        color: #3448b7;
        border-color: #d9e0ff;
      }
      .choice-option {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0;
        padding: 4px 6px;
        border-radius: 8px;
        border: 1px solid transparent;
        line-height: 1.25;
        position: relative;
        cursor: pointer;
      }
      
.choice-option .sr-only {
        position: absolute;
        opacity: 0;
        width: 1px;
        height: 1px;
        margin: 0;
        pointer-events: none;
      }
      
.radio-mark {
        width: 8px;
        height: 8px;
        flex: 0 0 8px;
        border: 1.5px solid #bcc8dd;
        border-radius: 50%;
        background: #fff;
        position: relative;
        box-sizing: border-box;
      }
      .choice-option:hover {
        background: #f6f9ff;
        border-color: #c9d7ff;
      }
      .choice-option input:focus-visible + .radio-mark {
        box-shadow: 0 0 0 2px rgba(37,99,235,.2);
      }
      .choice-option input:checked + .radio-mark {
        border-color: var(--primary);
      }
      
.radio-mark::after {
        content: '';
        position: absolute;
        width: 2px;
        height: 3px;
        top: 50%;
        left: 50%;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        background: transparent;
      }
      .choice-option input:checked + .radio-mark::after {
        background: var(--primary);
      }
      
      .choice-option .choice-text {
        font-size: 13px;
        margin: 0;
        line-height: 1.32;
      }
      #funds, #result { white-space: normal; }
      .small { color: var(--muted); font-size: 13px; }
      .ok { color: var(--ok); }
      .bad { color: var(--danger); }
            pre {
        max-height: 280px;
        overflow: auto;
        background: #0b1220;
        color: #edf2ff;
        border: 1px solid #1f2a44;
        padding: 12px;
        white-space: pre-wrap;
        border-radius: 10px;
      }
      .toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
      .actions-inline { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
      .doc-actions { margin-top: 10px; }
      .doc-actions .btn, .doc-actions .small-btn {
        width: fit-content;
      }
      .pill { display: inline-block; background: var(--primary-weak); color: #1e3a8a; border-radius: 999px; padding: 3px 10px; font-size: 12px; }
      .hidden { display: none; }

      .section-title {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 8px;
      }
      .section-title h3 { margin: 0; }
      .hint { color: var(--muted); font-size: 12px; }
      .controls { display: grid; grid-template-columns: minmax(180px, 1.2fr) minmax(170px, 1fr) auto auto; gap: 8px; margin-bottom: 10px; }
      #q, #managerFilter { min-width: 160px; }
      #q { width: 100%; }
      .funds-list { display: grid; gap: 10px; }
      .fund-item { padding: 12px; border: 1px solid var(--line); border-radius: 12px; background: #fff; transition: border-color .15s ease, box-shadow .15s ease; }
      .fund-item:hover { border-color: #bdd0ff; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06); }
      .fund-title { font-size: 15px; font-weight: 700; line-height: 1.35; margin-bottom: 8px; }
      .fund-meta { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; color: var(--muted); font-size: 13px; margin-bottom: 10px; }
      .fund-actions { display: flex; gap: 8px; flex-wrap: wrap; }
      .status-chip { display: inline-block; background: #eef2ff; color: #304ffe; padding: 3px 8px; border-radius: 999px; font-size: 11px; }
      .status-chip.disabled { background: #ffeaea; color: #b42318; }
      .inline-loading { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 13px; }
      .inline-loading::before { content: ''; width: 12px; height: 12px; border: 2px solid #d4dff3; border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      .question-header { font-size: 15px; margin-bottom: 8px; line-height: 1.35; }
      .result-item { border: 1px solid #e8edfa; border-radius: 10px; background: #fbfdff; padding: 10px; margin: 8px 0; }

      .doc-toolbar {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        align-items: baseline;
        margin-bottom: 10px;
      }
      .doc-summary {
        color: var(--muted);
        font-size: 12px;
        line-height: 1.3;
        text-align: right;
      }
      .doc-preview-wrap {
        border: 1px solid var(--line);
        border-radius: 12px;
        background: #0b1220;
        padding: 12px;
      }
      .doc-preview-wrap pre {
        margin: 0;
        max-height: 320px;
        overflow: auto;
        background: transparent;
        border: 0;
        color: #edf2ff;
        font-size: 12px;
        line-height: 1.45;
        white-space: pre-wrap;
      }

      .quiz-info {
        background: #f8faff;
        border: 1px solid #e2ebff;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
      }

      @media (max-width: 768px) {

        .row {
          gap: 6px;
          margin: 5px 0;
        }
        .btn, .small-btn {
          padding: 5px 8px;
          font-size: 11px;
          line-height: 1.15;
          min-height: auto;
        }
        .compact-btn {
          padding: 4px 7px !important;
          font-size: 10px !important;
        }
        .question {
          padding: 10px;
        }
        .choice-option {
          gap: 6px;
          line-height: 1.2;
          padding: 3px 5px;
        }
        .question {
          padding: 9px;
        }
        .quiz-info {
          flex-direction: column;
          align-items: flex-start;
        }
        
        .radio-mark {
          width: 12px;
          height: 12px;
          flex-basis: 12px;
        }
        .radio-mark::after {
          width: 2px;
          height: 2px;
        }
        .choice-option .choice-text {
          font-size: 10px;
          line-height: 1.08;
        }
      }
    </style>
  </head>
  <body>
    <div class="wrap">
    <h1>펀드 설명서 이해도 퀴즈</h1>
    <p class="subtitle">운용사·펀드별 공시를 기반으로 퀴즈를 만들고, 근거 문서를 바로 확인할 수 있어요.</p>

    <div class="card hidden" id="quizPanel">
      <h2>퀴즈</h2>
      <div id="quizStatus" class="small"></div>
      <div id="quizInfo"></div>
      <div id="quizMeta" class="quiz-info"></div>
      <form id="quizForm" onsubmit="submitQuiz(event)"></form>
      <div class="row">
        <button class="btn compact-btn" id="submitBtn" onclick="submitQuiz(event)">채점하기</button>
      </div>
      <div id="result"></div>
    </div>

    <div class="card hidden" id="docPanel">
      <h3>설명서 원문 미리보기</h3>
      <div class="doc-toolbar">
        <div id="docStatus" class="small">원문을 선택해 주세요.</div>
        <div id="docSummary" class="doc-summary"></div>
      </div>
      <div class="doc-preview-wrap">
        <pre id="docPreview"></pre>
      </div>
      <div id="docActions" class="row doc-actions"></div>
      <div class="row">
        <button class="small-btn compact-btn" type="button" onclick="hideDocPreview()">닫기</button>
      </div>
    </div>

    <div class="card">
      <div class="section-title"><h3>퀴즈 생성</h3>
        <span class="hint">운용사별로 수집된 펀드 목록에서 퀴즈를 생성합니다.</span>
      </div>
      <p>펀드명/운용사를 검색하고 선택하면 설명서 기반 퀴즈를 생성합니다.</p>
      <div class="controls">
        <input id="q" class="search-box" placeholder="펀드명/운용사 검색" />
        <select id="managerFilter"><option value="">전체 운용사</option></select>
        <button class="btn compact-btn" onclick="loadFunds()">검색</button>
        <button class="small-btn compact-btn" onclick="loadFunds(true)">전체 보기</button>
      </div>
      <div id="funds"></div>
    </div>

    <script>
      let currentQuiz = null;

      const quizCache = new Map();
      const pendingGenerate = new Map();
      const fundsCache = new Map();
      const disclosureLinkCache = new Map();
      let activeFundRequest = null;
      let autoBootstrapTriggered = false;
      let autoTopAiGenerated = false;
      let autoAiGenerateCount = 1;

      async function loadFunds(all = false) {
        const q = document.getElementById('q').value.trim();
        const manager = document.getElementById('managerFilter')?.value || '';
        const queryKey = `${all ? 'all' : 'search'}:${q || 'all'}:${manager || 'all'}`;

        // prevent duplicate concurrent requests for same query
        if (activeFundRequest === queryKey) {
          return;
        }
        if (fundsCache.has(queryKey)) {
          renderFunds(fundsCache.get(queryKey));
          return;
        }

        activeFundRequest = queryKey;
        const params = new URLSearchParams();
        if (q && !all) {
          params.set('q', q);
        }
        if (manager) {
          params.set('manager', manager);
        }

        const url = q && !all
          ? `/api/funds/search?${params.toString()}`
          : `/api/funds?${params.toString()}`;
        try {
          const resp = await fetch(url);
          const funds = await resp.json();
          fundsCache.set(queryKey, funds);
          renderFunds(funds);
        } catch (e) {
          document.getElementById('funds').innerHTML = `<p>상품 목록을 불러오지 못했습니다: ${escapeHtml(e.message || '오류')}</p>`;
        } finally {
          activeFundRequest = null;
        }
      }

      async function renderFunds(funds) {
        const wrap = document.getElementById('funds');
        if (!funds || !funds.length) {
          const q = document.getElementById('q').value.trim();
          const manager = document.getElementById('managerFilter')?.value || '';
          if (!q) {
            if (!autoBootstrapTriggered) {
              autoBootstrapTriggered = true;
              setTimeout(() => bootstrapSamples(), 100);
              wrap.innerHTML = '<div class="inline-loading">상품 데이터를 준비하고 있습니다.</div><p class="hint">데이터가 준비되면 바로 목록에 표시됩니다.</p>';
              return;
            }
            wrap.innerHTML = '<p>현재 표시할 상품이 없습니다.</p>' +
              '<p class="hint">동기화가 진행 중이거나 데이터가 준비되지 않았을 수 있어요.</p>' +
              '<button class="small-btn compact-btn" type="button" onclick="bootstrapSamples()">샘플 동기화 재시작</button>';
          } else {
            wrap.innerHTML = '<p>표시할 상품이 없습니다.</p>';
          }
          return;
        }
        wrap.innerHTML = `<div class="funds-list">${funds.map(f => `
          <article class="fund-item">
            <div class="fund-title">${escapeHtml(f.fund_name)}</div>
            <div class="fund-meta">
              <span>운용사: ${escapeHtml(f.manager_name || '-')}</span>
              <span>최신 공시: ${f.latest_disclosure_date || '-'}</span>
              <span>문항 준비: <span class="status-chip ${f.has_published_quiz ? '' : 'disabled'}">${f.has_published_quiz ? '준비됨' : '미생성'}</span></span>
            </div>
            <div class="fund-actions">
              <button class="btn compact-btn" type="button" data-fund="${f.fund_id}" onclick="openFund(${f.fund_id})">퀴즈</button>
              <button class="small-btn compact-btn" type="button" onclick="showDocumentPreview(${f.fund_id})">원문</button>
            </div>
          </article>
        `).join('')}
        </div>`;

        if (!autoTopAiGenerated && funds?.length > 0) {
          autoTopAiGenerated = true;
          const n = Math.max(0, Math.min(Number(autoAiGenerateCount || 1), 10));
          funds.slice(0, n).forEach((f) => {
            openFund(f.fund_id, { useAi: true, questionCount: 3 });
          });
        }
      }

      async function openFund(fundId, options = {}) {
        if (pendingGenerate.has(fundId)) {
          return;
        }

        const openBtn = document.querySelector(`button[data-fund='${fundId}']`);
        if (openBtn) {
          openBtn.disabled = true;
          openBtn.textContent = '진행중';
        }

        pendingGenerate.set(fundId, true);
        try {
          if (quizCache.has(fundId)) {
            const cached = quizCache.get(fundId);
            if (cached && cached.questions?.length > 0) {
              currentQuiz = cached;
              renderQuiz(cached);
              return;
            }
          }

          setQuizStatus('퀴즈 생성 요청 중...');
          const q = new URLSearchParams();
          if (typeof options.questionCount === 'number') {
            q.set('count', String(Math.min(Math.max(options.questionCount, 1), 10)));
          }
          if (options.force) {
            q.set('force', 'true');
          }
          if (options.useAi) {
            q.set('use_ai', 'true');
            q.set('force', 'true');
          }
          const qs = q.toString();
          const genResp = await fetch(`/api/funds/${fundId}/quiz/generate${qs ? '?' + qs : ''}`, { method: 'POST' });
          if (!genResp.ok) {
            const payload = await genResp.json().catch(() => ({}));
            throw new Error(payload.detail || '퀴즈 생성 요청 실패');
          }

          const quiz = await genResp.json();
          if (!quiz || !quiz.questions || quiz.questions.length === 0) {
            throw new Error('퀴즈가 아직 생성되지 않았습니다. 잠시 뒤 다시 시도하세요.');
          }

          quizCache.set(fundId, quiz);
          currentQuiz = quiz;
          setQuizStatus('퀴즈를 생성했습니다.');
          renderQuiz(quiz);
          document.getElementById('quizPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (err) {
          setQuizStatus(err?.message || '오류가 발생했습니다.');
          document.getElementById('quizPanel').classList.remove('hidden');
        } finally {
          pendingGenerate.delete(fundId);
          if (openBtn) {
            openBtn.disabled = false;
            openBtn.textContent = '퀴즈';
          }
        }
      }

      async function bootstrapSamples() {
        const wrap = document.getElementById('funds');
        wrap.innerHTML = '<p class="inline-loading">샘플 동기화 중...</p>';
        try {
          const r = await fetch('/api/sample/bootstrap', { method: 'POST' });
          const data = await r.json().catch(() => ({}));
          if (r.ok && data.started) {
            let tries = 0;
            const timer = setInterval(async () => {
              tries += 1;
              if (tries > 15) {
                clearInterval(timer);
                wrap.innerHTML = '<p>동기화가 지연되고 있습니다. 잠시 뒤 새로고침을 눌러주세요.</p>';
                return;
              }
              const st = await fetch('/api/sample/bootstrap-status').then(x => x.json()).catch(() => ({ inflight: false }));
              if (!st.inflight) {
                clearInterval(timer);
                loadFunds(true);
              }
            }, 4000);
          } else if (data.started === false) {
            wrap.innerHTML = '<p>이미 샘플 동기화가 진행 중입니다.</p>';
          } else {
            wrap.innerHTML = '<p>샘플 동기화 요청 실패</p>';
          }
        } catch (_e) {
          wrap.innerHTML = '<p>샘플 동기화 요청 실패</p>';
        }
      }

      async function loadManagers() {
        const sel = document.getElementById('managerFilter');
        if (!sel) return;
        sel.innerHTML = '<option value="">전체 운용사</option>';
        try {
          const resp = await fetch('/api/managers?limit=500');
          const items = await resp.json();
          (items || []).forEach((name) => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            sel.appendChild(option);
          });

        } catch (_e) {
          // keep default
        }
      }

      async function showDocumentPreview(fundId) {
        const panel = document.getElementById('docPanel');
        const status = document.getElementById('docStatus');
        const output = document.getElementById('docPreview');
        const actions = document.getElementById('docActions');
        const summary = document.getElementById('docSummary');
        if (!panel || !status || !output || !actions) {
          return;
        }

        panel.classList.remove('hidden');
        status.textContent = '원문을 불러오는 중...';
        if (summary) {
          summary.textContent = '로딩 중';
        }
        output.textContent = '';
        actions.innerHTML = '';
        try {
          const resp = await fetch(`/api/funds/${fundId}/document-preview`);
          const data = await resp.json();
          if (!resp.ok) {
            throw new Error(data?.detail || '원문 조회 실패');
          }

          const hasPreview = data.block_count > 0 && data.download_url;
          const downloadButton = hasPreview
            ? `<a class="small-btn compact-btn" href="${data.download_url}" target="_blank" rel="noopener">원문 텍스트</a>`
            : '';
          const viewButton = data.viewer_url
            ? `<a class="small-btn compact-btn" href="${data.viewer_url}" target="_blank" rel="noopener">공시 페이지</a>`
            : '';

          const buttons = [];
          if (downloadButton) buttons.push(downloadButton);
          if (viewButton) buttons.push(viewButton);

          status.textContent = '원문 미리보기';
          if (summary) {
            summary.textContent = `공시번호: ${data.rcept_no || '-'}  /  블록수: ${data.block_count}`;
          }
          actions.innerHTML = buttons.join('');
          const text = (data.preview || '').trim();
          output.textContent = text || '원문 추출 데이터가 아직 없습니다.';
          status.className = 'small';
          panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (err) {
          status.className = 'small bad';
          status.textContent = err?.message || '원문 조회 실패';
          if (summary) {
            summary.textContent = '';
          }
          output.textContent = '';
          actions.innerHTML = '';
        }
      }

      function hideDocPreview() {
        const panel = document.getElementById('docPanel');
        const actions = document.getElementById('docActions');
        if (actions) {
          actions.innerHTML = '';
        }
        if (panel) {
          panel.classList.add('hidden');
        }
      }

      function renderQuiz(quiz) {
        const form = document.getElementById('quizForm');
        const meta = document.getElementById('quizMeta');
        const info = document.getElementById('quizInfo');
        const quizTitle = `${escapeHtml(quiz.title || '퀴즈')}`;
        const qCount = Number(quiz.question_count || 0);

        if (info) {
          info.textContent = `${quizTitle} (${qCount}문항)`;
        }
        if (meta) {
          meta.innerHTML = `<div class="quiz-meta"><span>문항 수: ${qCount}</span><span>진행 방식: 선다형</span></div>`;
        }

        form.innerHTML = '';
        quiz.questions.forEach((q, idx) => {
          const block = document.createElement('div');
          block.className = 'question';
          const diff = formatDifficultyChip(q.difficulty);
          block.innerHTML = `<div class="question-header"><strong>${idx + 1}. ${escapeHtml(q.prompt)}</strong> ${diff}</div>`;
          const choices = document.createElement('div');
          choices.className = 'choices';
          q.choices.forEach((c, ci) => {
            const id = `q-${idx}-${ci}`;
            choices.innerHTML += `
              <label class="choice-option">
                <input class="sr-only" type="radio" id="${id}" name="q${idx}" value="${ci}" />
                <span class="radio-mark" aria-hidden="true"></span>
                <span class="choice-text">${escapeHtml(c)}</span>
              </label>`;
          });
          block.appendChild(choices);
          form.appendChild(block);
        });
        document.getElementById('quizPanel').classList.remove('hidden');
        document.getElementById('result').innerHTML = '';
      }

      async function submitQuiz(event) {
        event.preventDefault();
        if (!currentQuiz) return;

        const answers = [];
        currentQuiz.questions.forEach((_, idx) => {
          const v = document.querySelector(`input[name="q${idx}"]:checked`);
          answers.push(v ? Number(v.value) : -1);
        });

        const resp = await fetch('/api/quiz-attempts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ quiz_id: currentQuiz.quiz_id, answers }),
        });

        const data = await resp.json();
        const html = [`<h3>채점 결과: ${data.score}/${data.total}</h3>`];
        const viewerUrl = await getDisclosureViewerUrl(currentQuiz.disclosure_id);
        for (let i = 0; i < currentQuiz.questions.length; i += 1) {
          const q = currentQuiz.questions[i];
          const ok = data.correct?.[i] ? '정답' : '오답';
          const badge = ok === '정답' ? 'status-chip' : 'status-chip disabled';
          const explanation = escapeHtml(cleanExplanation(q.explanation || ''));
          const docLinkHtml = viewerUrl
            ? `<div class="small" style="margin-top:8px;"><a class="small-btn compact-btn" href="${viewerUrl}" target="_blank" rel="noopener">공시 링크</a></div>`
            : `<div class="small" style="margin-top:8px;">공시 링크를 불러오지 못했습니다.</div>`;
          html.push(`<div class="result-item"><div><strong>문항 ${i + 1}</strong> <span class="${badge}">${ok}</span></div><div>해설: ${explanation}</div>${docLinkHtml}</div>`);
        }
        const resultEl = document.getElementById('result');
        if (resultEl) {
          resultEl.innerHTML = html.join('');
        }
      }

      function formatDifficultyChip(raw) {
        const key = String(raw || '').toLowerCase();
        const map = {
          easy: { label: 'Easy', icon: '🟢', cls: 'easy' },
          medium: { label: 'Medium', icon: '🟠', cls: 'medium' },
          hard: { label: 'Hard', icon: '🔴', cls: 'hard' },
        };
        const item = map[key] || { label: raw || 'Unknown', icon: '⚪', cls: 'unknown' };
        return `<span class="difficulty-chip ${item.cls}">${item.icon} ${escapeHtml(item.label)}</span>`;
      }

      function resolveSourceRefs(sourceRefs, index, fallback) {
        if (sourceRefs && Array.isArray(sourceRefs[index])) {
          return sourceRefs[index];
        }
        if (sourceRefs && Array.isArray(sourceRefs[String(index)])) {
          return sourceRefs[String(index)];
        }
        if (Array.isArray(fallback)) {
          return fallback;
        }
        return [];
      }

      function resolveSourceSnippets(sourceSnippets, index) {
        if (sourceSnippets && Array.isArray(sourceSnippets[index])) {
          return sourceSnippets[index];
        }
        if (sourceSnippets && Array.isArray(sourceSnippets[String(index)])) {
          return sourceSnippets[String(index)];
        }
        return [];
      }

      function cleanExplanation(text) {
        return String(text || '')
          .replace(/문서에서\s*근거\s*:\s*span_\d+/gi, '')
          .replace(/\s+/g, ' ')
          .trim() || '해설이 제공되지 않았습니다.';
      }

      function formatSnippet(text) {
        const oneLine = String(text || '').replace(/\s+/g, ' ').trim();
        if (oneLine.length <= 220) return oneLine;
        return oneLine.slice(0, 220) + '…';
      }

      async function getDisclosureViewerUrl(fundId) {
        if (disclosureLinkCache.has(fundId)) {
          return disclosureLinkCache.get(fundId);
        }
        try {
          const resp = await fetch(`/api/funds/${fundId}/document-preview`);
          const data = await resp.json();
          const url = data?.viewer_url || '';
          disclosureLinkCache.set(fundId, url);
          return url;
        } catch (_e) {
          return '';
        }
      }

      async function loadUiConfig() {
        try {
          const resp = await fetch('/api/ui-config');
          const cfg = await resp.json();
          autoAiGenerateCount = Math.max(0, Math.min(Number(cfg?.auto_ai_generate_count || 1), 10));
        } catch (_e) {
          autoAiGenerateCount = 1;
        }
      }

      function setQuizStatus(message, isError = false) {
        const el = document.getElementById('quizStatus');
        if (!el) return;
        el.textContent = message || '';
        el.className = 'small ' + (isError ? 'bad' : 'ok');
      }

      function escapeHtml(value) {
        return String(value)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#039;');
      }

      document.addEventListener('DOMContentLoaded', () => {
        setQuizStatus('');
        loadUiConfig().then(() => {
          loadManagers().then(() => {
            loadFunds(true);
          });
        });

        const managerEl = document.getElementById('managerFilter');
        if (managerEl) {
          managerEl.addEventListener('change', () => loadFunds(true));
        }
      });
    </script>
      </div>
  </body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return HTML_LANDING


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(public.router)
app.include_router(admin.router)

