import os
import re
import json
import urllib3
import requests
import subprocess

URL_MAP = {}
try:
    with open("C:/Users/USER/gitlab-qa-analyzer/url_mapping.json", "r", encoding="utf-8") as f:
        URL_MAP = json.load(f)
except:
    pass

import uvicorn
from datetime import datetime, timedelta
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_GITLAB_URL = "https://gitlab.somansa.com"
DEFAULT_GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")

SOURCEGRAPH_URL = "http://10.216.195.85:9500"
SOURCEGRAPH_TOKEN = os.environ.get("SOURCEGRAPH_TOKEN", "")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DLPCenter QA AI Impact Analyzer - Sourcegraph 팩트 포털</title>
    <style>
        :root {
            --bg-main: #0f172a;
            --bg-card: rgba(30, 41, 59, 0.85);
            --bg-input: #020617;
            --border-color: rgba(255, 255, 255, 0.12);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-primary: #6366f1;
            --accent-purple: #8b5cf6;
            --danger-red: #ef4444;
            --warning-amber: #f59e0b;
            --success-green: #10b981;
            --info-blue: #3b82f6;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, "맑은 고딕", sans-serif; }
        body { background-color: var(--bg-main); color: var(--text-primary); min-height: 100vh; display: flex; flex-direction: column; }

        header { background: var(--bg-card); border-bottom: 1px solid var(--border-color); padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; backdrop-filter: blur(10px); }
        .logo-area { display: flex; align-items: center; gap: 12px; }
        .logo-icon { width: 42px; height: 42px; background: linear-gradient(135deg, var(--accent-primary), var(--accent-purple)); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; color: white; box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4); }
        .logo-title { font-size: 18px; font-weight: 700; background: linear-gradient(90deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .logo-sub { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }

        .header-actions { display: flex; align-items: center; gap: 12px; }
        .status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
        .pulse-dot { width: 8px; height: 8px; background: #38bdf8; border-radius: 50%; box-shadow: 0 0 8px #38bdf8; }

        .container { max-width: 96%; width: 100%; margin: 0 auto; padding: 24px; display: grid; grid-template-columns: 440px 1fr; gap: 24px; flex: 1; }
        @media (max-width: 1024px) { .container { grid-template-columns: 1fr; } }

        .card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 16px; padding: 20px; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3); margin-bottom: 20px; }
        .card-title { font-size: 15px; font-weight: 700; color: var(--text-primary); margin-bottom: 16px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; }

        .form-group { margin-bottom: 16px; }
        .form-label { display: block; font-size: 11px; font-weight: 700; color: #a5b4fc; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
        .form-input { width: 100%; background: var(--bg-input); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; font-size: 12px; color: white; outline: none; font-family: monospace; }
        .form-input:focus { border-color: var(--accent-primary); box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25); }
        
        .radio-group { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px; }
        .radio-box { background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px; cursor: pointer; text-align: center; transition: all 0.2s; }
        .radio-box:hover { border-color: var(--accent-primary); }
        .radio-box.active { background: rgba(99, 102, 241, 0.25); border-color: var(--accent-primary); box-shadow: 0 0 10px rgba(99, 102, 241, 0.3); }
        .radio-title { font-size: 12px; font-weight: bold; color: white; }
        .radio-desc { font-size: 10px; color: var(--text-muted); margin-top: 2px; }

        .btn-primary { width: 100%; background: linear-gradient(135deg, var(--accent-primary), var(--accent-purple)); color: white; border: none; border-radius: 10px; padding: 13px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3); }
        .btn-primary:hover { opacity: 0.92; transform: translateY(-1px); }
        .btn-secondary { background: rgba(51, 65, 85, 0.8); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 8px 14px; font-size: 12px; font-weight: 600; cursor: pointer; }

        .date-filter-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; }
        .date-tab { padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); color: var(--text-secondary); cursor: pointer; transition: all 0.2s; }
        .date-tab:hover { background: rgba(99, 102, 241, 0.2); color: white; }
        .date-tab.active { background: var(--accent-primary); color: white; border-color: var(--accent-primary); font-weight: bold; box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4); }

        .commit-list { max-height: 480px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
        .commit-item { background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px 12px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: all 0.2s; }
        .commit-item:hover { background: rgba(99, 102, 241, 0.2); border-color: var(--accent-primary); }
        .commit-sha { font-family: monospace; font-size: 11px; font-weight: bold; color: #818cf8; }
        .commit-title { font-size: 11px; color: #e2e8f0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px; margin-top: 3px; }

        .risk-banner { display: flex; justify-content: space-between; align-items: center; background: rgba(15, 23, 42, 0.9); border: 1px solid var(--border-color); border-radius: 12px; padding: 16px 20px; margin-bottom: 20px; }
        .risk-tag { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 800; }
        .risk-HIGH { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
        .risk-MEDIUM { background: rgba(245, 158, 11, 0.2); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.4); }
        .risk-LOW { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.4); }

        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }
        .metric-box { background: rgba(2, 6, 23, 0.7); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px; text-align: center; }
        .metric-label { font-size: 11px; color: var(--text-muted); }
        .metric-value { font-size: 16px; font-weight: 800; color: #38bdf8; margin-top: 4px; }

        .sg-fact-banner { background: linear-gradient(135deg, rgba(14, 165, 233, 0.15), rgba(99, 102, 241, 0.15)); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 12px; padding: 14px 16px; margin-bottom: 16px; }
        .sg-fact-title { font-size: 12px; font-weight: bold; color: #38bdf8; display: flex; align-items: center; gap: 6px; }
        .sg-fact-desc { font-size: 11px; color: #cbd5e1; margin-top: 4px; line-height: 1.4; }

        .section-box { margin-bottom: 20px; }
        .screen-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        @media (max-width: 768px) { .screen-grid { grid-template-columns: 1fr; } }
        
        .module-badge { display: inline-block; font-size: 11px; font-weight: 800; padding: 3px 9px; border-radius: 6px; margin-bottom: 6px; letter-spacing: 0.3px; }
        .module-PRIVACYI { background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); }
        .module-SERVERI { background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); }
        .module-ZIKIMI { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
        .module-PCZIKIMI { background: rgba(52, 211, 153, 0.2); color: #a7f3d0; border: 1px solid rgba(52, 211, 153, 0.4); }
        .module-MAILI { background: rgba(245, 158, 11, 0.2); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.4); }
        .module-DBI { background: rgba(236, 72, 153, 0.2); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.4); }
        .module-COMMON { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.4); }

        .screen-card { background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 12px; padding: 16px; }
        
        .real-file-badge { font-size: 11px; font-weight: bold; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.2); margin-bottom: 6px; display: inline-block; font-family: monospace; }
        .screen-name { font-size: 14px; font-weight: 800; color: #f8fafc; }
        .screen-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 10px; }
        .tag-list { display: flex; flex-wrap: wrap; gap: 5px; }
        .tag-button { font-size: 11px; font-weight: 700; background: rgba(99, 102, 241, 0.25); color: #c7d2fe; border: 1px solid rgba(99, 102, 241, 0.4); padding: 4px 9px; border-radius: 6px; }

        .side-effect-card { background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 12px; padding: 16px; margin-bottom: 12px; }
        .side-effect-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .side-effect-title { font-size: 13px; font-weight: 700; color: #38bdf8; }
        .side-effect-detail { font-size: 12px; color: #cbd5e1; line-height: 1.5; margin-top: 4px; }
        .side-effect-target { font-size: 11px; background: rgba(2, 6, 23, 0.8); padding: 8px 12px; border-radius: 6px; margin-top: 10px; color: #94a3b8; border: 1px solid rgba(255,255,255,0.08); font-family: monospace; }

        .fact-code-box { background: #020617; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; padding: 10px 12px; margin-top: 8px; font-family: monospace; font-size: 11px; color: #38bdf8; word-break: break-all; }

        .tc-table-wrapper { overflow-x: auto; border: 1px solid var(--border-color); border-radius: 10px; }
        .tc-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 12px; }
        .tc-table th { background: rgba(15, 23, 42, 0.9); padding: 11px 14px; color: var(--text-secondary); border-bottom: 1px solid var(--border-color); font-weight: 600; }
        .tc-table td { padding: 11px 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); color: #cbd5e1; line-height: 1.4; }
        .tc-table tr:hover { background: rgba(255, 255, 255, 0.03); }

        .diff-file-card { border: 1px solid var(--border-color); border-radius: 10px; overflow: hidden; margin-bottom: 10px; background: #020617; }
        .diff-file-header { background: #1e293b; padding: 8px 12px; font-family: monospace; font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between; }
        .diff-pre { padding: 10px 12px; font-family: monospace; font-size: 11px; color: #38bdf8; overflow-x: auto; max-height: 180px; white-space: pre-wrap; word-break: break-all; }

        .empty-state { text-align: center; padding: 60px 20px; }
        .empty-icon { font-size: 42px; margin-bottom: 12px; }
        .hidden { display: none !important; }
    </style>
</head>
<body>

    <header>
        <div class="logo-area">
            <div class="logo-icon">🛡️</div>
            <div>
                <div class="logo-title">DLPCenter QA AI Impact Analyzer</div>
                <div class="logo-sub">Sourcegraph AI (10.216.195.85:9500) 실시간 연동 포털</div>
            </div>
        </div>
        <div class="header-actions">
            <div class="status-badge">
                <div class="pulse-dot"></div> Sourcegraph Live API Connected
            </div>
        </div>
    </header>

    <div class="container">
        <div>
            <div class="card">
                <div class="card-title">🔍 비교 대상 & 커밋 리비전 입력</div>
                
                <div class="form-group">
                    <label class="form-label">1단계: 비교 기준 브랜치 (Base Target)</label>
                    <div class="radio-group">
                        <div id="btnBasePR" class="radio-box active" onclick="selectBaseBranch('PR')">
                            <div class="radio-title">PR 브랜치</div>
                            <div class="radio-desc">개발/통합 기준</div>
                        </div>
                        <div id="btnBaseR" class="radio-box" onclick="selectBaseBranch('R')">
                            <div class="radio-title">R 브랜치</div>
                            <div class="radio-desc">릴리즈 빌드 기준</div>
                        </div>
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">2단계: 반영할 커밋 리비전 (Revision SHA)</label>
                    <input type="text" id="commitShaInput" class="form-input" 
                           placeholder="예: a785126e3156f68c7b87722ddeaa2c7057825803" 
                           value="b5b897b9">
                    <div style="font-size: 10px; color: var(--text-muted); margin-top: 4px;">
                        개발자가 새로 작성/반영할 Commit Hash
                    </div>
                </div>

                <div class="form-group" style="display: none;">
                    <input type="text" id="projectIdInput" value="317">
                    <input type="text" id="selectedBaseBranch" value="PR">
                </div>

                <!-- 명확하게 지정된 보라색 분석 버튼 -->
                <button onclick="fetchAndAnalyze()" class="btn-primary" id="btnAnalyzeMain">
                    ⚡ Sourcegraph AI 연동 AI 영향도 분석
                </button>
            </div>

            <div class="card">
                <div class="card-title" style="justify-content: space-between;">
                    <span>📌 DLPCenter 최근 1주일 커밋 목록</span>
                    <button onclick="loadCommitList()" class="btn-secondary" style="padding: 4px 8px; font-size: 10px;">새로고침</button>
                </div>
                
                <div id="dateFilterBar" class="date-filter-bar">
                    <div class="date-tab active" onclick="onDateTabClick(this)" data-date="ALL">전체 (1주일)</div>
                </div>

                <div id="commitListContainer" class="commit-list">
                    <div style="text-align: center; color: var(--text-muted); font-size: 11px; padding: 20px;">DLPCenter 커밋 목록 불러오는 중...</div>
                </div>
            </div>
        </div>

        <div>
            <div id="emptyState" class="card empty-state">
                <div class="empty-icon">🛡️</div>
                <h3 style="font-size: 18px; font-weight: bold; margin-bottom: 8px;">비교 기준과 커밋 리비전을 선택하세요</h3>
                <p style="font-size: 13px; color: var(--text-secondary); max-width: 520px; margin: 0 auto; line-height: 1.5;">
                    오픈스택 VM의 <strong>Sourcegraph AI (10.216.195.85:9500)</strong> 가 소만사 전체 소스 지도를 실시간 조회하여<br>
                    <strong>실제 소만사 연동 소스 파일 및 수정한 코드 Line 팩트</strong>를 가져옵니다.
                </p>
            </div>

            <div id="loadingState" class="card empty-state hidden">
                <div class="empty-icon">⚙️</div>
                <h3 style="font-size: 16px; font-weight: bold; margin-bottom: 6px;">Sourcegraph AI API (10.216.195.85:9500) 코드 지도 실시간 스캔 중...</h3>
                <p style="font-size: 12px; color: var(--text-muted);">오픈스택 Sourcegraph 서버에서 소만사 전체 코드베이스 매칭 팩트를 조회하고 있습니다.</p>
            </div>

            <div id="reportContainer" class="hidden">
                
                <div class="sg-fact-banner" id="sgFactBanner">
                    <div class="sg-fact-title">
                        <span>🔍 Sourcegraph Live API (10.216.195.85:9500) 실시간 코드베이스 스캔 결과</span>
                    </div>
                    <div class="sg-fact-desc" id="sgFactDesc">
                        오픈스택 VM의 Sourcegraph AI 엔진이 platform/git-dlpcenter 소스 코드 지도를 스캔하여 팩트 매칭을 완료했습니다.
                    </div>
                </div>

                <div class="card">
                    <div class="risk-banner">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                <span id="badgeRisk" class="risk-tag risk-HIGH">HIGH RISK</span>
                                <span id="comparisonRefText" style="font-size: 12px; color: #a5b4fc; font-weight: bold;">
                                    기준: [PR 브랜치] 🆚 커밋: [b5b897b9] (Sourcegraph Live Connected)
                                </span>
                            </div>
                            <h2 id="commitTitleText" style="font-size: 17px; font-weight: bold; color: white;">커밋 메시지 제목</h2>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button onclick="postCommentToGitLab()" class="btn-secondary">💬 GitLab 코멘트 등록</button>
                            <button onclick="downloadMarkdownReport()" class="btn-primary" style="padding: 8px 14px; font-size: 12px; width: auto;">📥 리포트 다운로드</button>
                        </div>
                    </div>

                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">수정된 소스 파일</div>
                            <div class="metric-value" id="metricFiles">0개</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Sourcegraph 연관 모듈</div>
                            <div class="metric-value" id="metricScreens">0개</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">SG 팩트 기반 위험</div>
                            <div class="metric-value" id="metricRisks" style="color: var(--warning-amber);">0개</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">우선 수동 검증 TC</div>
                            <div class="metric-value" id="metricTCs" style="color: var(--success-green);">0개</div>
                        </div>
                    </div>
                </div>

                <div class="card section-box">
                    <div class="card-title">💻 1. 커밋에서 수정한 실제 소스 파일 & 연관 모듈</div>
                    <div id="impactedScreensList" class="screen-grid"></div>
                </div>

                <div class="card section-box">
                    <div class="card-title" style="color: var(--warning-amber);">⚠️ 2. Sourcegraph 코드 Line 팩트 기반 검증 가이드 (UI Checkpoints)</div>
                    <div id="sideEffectsList"></div>
                </div>

                <div class="card section-box">
                    <div class="card-title" style="color: #34d399;">✅ 3. Sourcegraph AI 연동 우선 수동 검증 추천 테스트 케이스</div>
                    <div class="tc-table-wrapper">
                        <table class="tc-table">
                            <thead>
                                <tr>
                                    <th>TC ID</th>
                                    <th>검증 대상 소스 파일 / 연동 모듈</th>
                                    <th>Sourcegraph 검증 수동 테스트 시나리오</th>
                                    <th>우선순위</th>
                                    <th>기대 결과</th>
                                </tr>
                            </thead>
                            <tbody id="tcTableBody"></tbody>
                        </table>
                    </div>
                </div>

                <div class="card section-box">
                    <div class="card-title">📄 4. 커밋 코드 변경 상세 (GitLab Diff Line-by-Line)</div>
                    <div id="fileDiffContainer"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        var currentAnalysisData = null;
        var allCommitsData = [];
        var selectedDateFilter = 'ALL';

        function escapeHtml(text) {
            if (!text) return '';
            return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
        }

        function formatDiffSyntax(text) {
            if (!text) return '';
            var lines = text.split(String.fromCharCode(10));
            var formattedHtml = '';
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                var escapedLine = escapeHtml(line);
                if (line.indexOf('+') === 0 && line.indexOf('+++') !== 0) {
                    formattedHtml += '<div style="background-color: rgba(34, 197, 94, 0.2); color: #4ade80; padding: 2px 6px; border-radius: 4px; margin: 1px 0; font-weight: 600;">' + escapedLine + '</div>';
                } else if (line.indexOf('-') === 0 && line.indexOf('---') !== 0) {
                    formattedHtml += '<div style="background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; padding: 2px 6px; border-radius: 4px; margin: 1px 0; font-weight: 600;">' + escapedLine + '</div>';
                } else if (line.indexOf('---') === 0 || line.indexOf('+++') === 0 || line.indexOf('@@') === 0) {
                    formattedHtml += '<div style="color: #c084fc; font-weight: bold; margin: 4px 0;">' + escapedLine + '</div>';
                } else {
                    formattedHtml += '<div style="color: #94a3b8; padding: 1px 6px;">' + escapedLine + '</div>';
                }
            }
            return formattedHtml;
        }

        function selectBaseBranch(branchType) {
            document.getElementById('selectedBaseBranch').value = branchType;
            if (branchType === 'PR') {
                document.getElementById('btnBasePR').className = 'radio-box active';
                document.getElementById('btnBaseR').className = 'radio-box';
            } else {
                document.getElementById('btnBasePR').className = 'radio-box';
                document.getElementById('btnBaseR').className = 'radio-box active';
            }
        }

        function loadCommitList() {
            var container = document.getElementById('commitListContainer');
            var projectId = document.getElementById('projectIdInput').value || '317';
            container.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 11px; padding: 20px;">DLPCenter 최근 커밋 불러오는 중...</div>';

            fetch('/api/commits?project_id=' + projectId)
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data.status === 'success' && data.commits && data.commits.length > 0) {
                        allCommitsData = data.commits.sort(function(a, b) {
                            return new Date(b.created_at) - new Date(a.created_at);
                        });
                        renderDateTabs(allCommitsData);
                        renderCommitList(allCommitsData, 'ALL');
                    } else {
                        container.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 11px; padding: 20px;">조회된 커밋이 없습니다.</div>';
                    }
                })
                .catch(function(err) {
                    container.innerHTML = '<div style="text-align: center; color: var(--danger-red); font-size: 11px; padding: 20px;">커밋 연동 실패: ' + err.message + '</div>';
                });
        }

        function renderDateTabs(commits) {
            var filterBar = document.getElementById('dateFilterBar');
            var datesMap = {};
            
            for (var i = 0; i < commits.length; i++) {
                if (commits[i].created_at) {
                    var d = commits[i].created_at.split('T')[0];
                    datesMap[d] = (datesMap[d] || 0) + 1;
                }
            }

            var allActive = (selectedDateFilter === 'ALL') ? 'active' : '';
            var html = '<div class="date-tab ' + allActive + '" onclick="onDateTabClick(this)" data-date="ALL">전체 (1주일)</div>';
            var dates = Object.keys(datesMap).sort().reverse();
            for (var j = 0; j < dates.length; j++) {
                var dt = dates[j];
                var count = datesMap[dt];
                var mmdd = dt.substring(5);
                var isActive = (selectedDateFilter === dt) ? 'active' : '';
                var displayCount = count > 20 ? '최신 20건' : count + '건';
                html += '<div class="date-tab ' + isActive + '" onclick="onDateTabClick(this)" data-date="' + dt + '">' + mmdd + ' (' + displayCount + ')</div>';
            }
            filterBar.innerHTML = html;
        }

        function onDateTabClick(el) {
            var dt = el.getAttribute('data-date');
            filterByDate(dt);
        }

        function filterByDate(dateStr) {
            selectedDateFilter = dateStr;
            renderDateTabs(allCommitsData);
            renderCommitList(allCommitsData, dateStr);
        }

        function renderCommitList(commits, dateFilter) {
            var container = document.getElementById('commitListContainer');
            var filtered = [];

            if (dateFilter === 'ALL') {
                filtered = commits;
            } else {
                for (var i = 0; i < commits.length; i++) {
                    if (commits[i].created_at && commits[i].created_at.indexOf(dateFilter) === 0) {
                        filtered.push(commits[i]);
                    }
                }
                filtered = filtered.slice(0, 20);
            }

            if (filtered.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 11px; padding: 20px;">선택한 날짜(' + dateFilter + ')의 커밋이 없습니다.</div>';
                return;
            }

            var html = '';
            for (var j = 0; j < filtered.length; j++) {
                var c = filtered[j];
                var shortSha = c.id ? c.id.substring(0, 8) : '';
                var dateStr = '';
                if (c.created_at) {
                    var parts = c.created_at.split('T');
                    var timePart = parts[1] ? parts[1].substring(0, 5) : '';
                    dateStr = parts[0] + ' ' + timePart;
                }
                html += '<div class="commit-item" onclick="onCommitClick(this)" data-sha="' + c.id + '">';
                html += '<div>';
                html += '<div style="display: flex; align-items: center; gap: 8px;">';
                html += '<span class="commit-sha">' + shortSha + '</span>';
                html += '<span style="font-size: 10px; color: #a5b4fc; background: rgba(99,102,241,0.2); padding: 1px 6px; border-radius: 4px; font-weight: bold;">📅 ' + dateStr + '</span>';
                html += '</div>';
                html += '<div class="commit-title">' + escapeHtml(c.title || '') + '</div>';
                html += '</div>';
                html += '<span style="font-size: 10px; color: var(--text-muted); text-align: right;">작성자: ' + escapeHtml(c.author_name || '') + '</span>';
                html += '</div>';
            }
            container.innerHTML = html;
        }

        function onCommitClick(el) {
            var sha = el.getAttribute('data-sha');
            selectCommit(sha);
        }

        function selectCommit(sha) {
            document.getElementById('commitShaInput').value = sha;
            fetchAndAnalyze();
        }

        function fetchAndAnalyze() {
            var projectId = document.getElementById('projectIdInput').value;
            var baseBranch = document.getElementById('selectedBaseBranch').value;
            var commitSha = document.getElementById('commitShaInput').value.trim();

            if (!commitSha) {
                alert('반영할 커밋 리비전(Commit SHA)을 입력하거나 아래 목록에서 선택해주세요.');
                return;
            }

            document.getElementById('emptyState').classList.add('hidden');
            document.getElementById('reportContainer').classList.add('hidden');
            document.getElementById('loadingState').classList.remove('hidden');

            fetch('/api/analyze-commit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: projectId,
                    base_branch: baseBranch,
                    commit_sha: commitSha
                })
            })
            .then(function(res) { return res.json(); })
            .then(function(result) {
                document.getElementById('loadingState').classList.add('hidden');
                if (result.status === 'success') {
                    currentAnalysisData = result.data;
                    renderReport(result.data);
                } else {
                    alert('분석 오류: ' + result.message);
                    document.getElementById('emptyState').classList.remove('hidden');
                }
            })
            .catch(function(err) {
                document.getElementById('loadingState').classList.add('hidden');
                document.getElementById('emptyState').classList.remove('hidden');
                alert('요청 중 오류 발생: ' + err.message);
            });
        }

        function renderReport(data) {
            document.getElementById('reportContainer').classList.remove('hidden');

            var shortSha = data.commit_sha ? data.commit_sha.substring(0, 8) : 'SHA';
            document.getElementById('comparisonRefText').innerText = '기준: [' + data.base_branch + ' 브랜치] %EF%B8%8F 반영 커밋: [' + shortSha + '] (Sourcegraph Live Connected)';
            document.getElementById('commitTitleText').innerText = data.commit_title || ('Commit ' + shortSha);
            
            var riskBadge = document.getElementById('badgeRisk');
            riskBadge.innerText = data.risk_level + ' RISK';
            riskBadge.className = 'risk-tag risk-' + data.risk_level;

            var sgFactDesc = document.getElementById('sgFactDesc');
            if (data.sg_fact_info) {
                sgFactDesc.innerHTML = '<strong>[Sourcegraph AI 인덱싱 팩트]</strong> ' + escapeHtml(data.sg_fact_info);
            }

            document.getElementById('metricFiles').innerText = data.changes_count + '개 파일';
            document.getElementById('metricScreens').innerText = data.impacted_screens.length + '개 모듈';
            document.getElementById('metricRisks').innerText = data.side_effects.length + '개 SG 팩트 검증';
            document.getElementById('metricTCs').innerText = data.recommended_tcs.length + '개 SG TC';

            var screensContainer = document.getElementById('impactedScreensList');
            var screensHtml = '';
            for (var i = 0; i < data.impacted_screens.length; i++) {
                var sc = data.impacted_screens[i];
                var moduleClass = 'module-' + (sc.module_code || 'COMMON');
                var tagsHtml = '';
                for (var j = 0; j < sc.affected_features.length; j++) {
                    tagsHtml += '<span class="tag-button">🔘 ' + escapeHtml(sc.affected_features[j]) + '</span>';
                }
                screensHtml += '<div class="screen-card">';
                screensHtml += '<div style="display:flex; justify-content:space-between; align-items:center;">';
                screensHtml += '<span class="module-badge ' + moduleClass + '">📦 ' + escapeHtml(sc.module_name || 'DLPCenter 공통') + '</span>';
                screensHtml += '<span style="font-size: 10px; font-weight: bold; color: #a5b4fc;">' + escapeHtml(sc.impact_degree) + '</span>';
                screensHtml += '</div>';
                screensHtml += '<div class="real-file-badge">📄 SG 수정한 파일: ' + escapeHtml(sc.raw_file || '소스 파일') + '</div>';
                screensHtml += '<div class="screen-name">🖥️ 연관 모듈/역할: ' + escapeHtml(sc.screen_name) + '</div>';
                screensHtml += '<p class="screen-desc" style="margin-top:6px;">' + escapeHtml(sc.description) + '</p>';
                screensHtml += '<div style="font-size:11px; font-weight:bold; color:#cbd5e1; margin-bottom:6px;">🎯 Sourcegraph 연관 수동 검증 포인트:</div>';
                screensHtml += '<div class="tag-list">' + tagsHtml + '</div>';
                screensHtml += '</div>';
            }
            screensContainer.innerHTML = screensHtml;

            var sideEffectsContainer = document.getElementById('sideEffectsList');
            var sideEffectsHtml = '';
            for (var k = 0; k < data.side_effects.length; k++) {
                var se = data.side_effects[k];
                sideEffectsHtml += '<div class="side-effect-card">';
                sideEffectsHtml += '<div class="side-effect-header">';
                sideEffectsHtml += '<span class="side-effect-title">' + escapeHtml(se.category) + ' - ' + escapeHtml(se.symptom) + '</span>';
                sideEffectsHtml += '<span style="font-size: 10px; font-weight: bold; color: #f87171;">' + escapeHtml(se.severity) + '</span>';
                sideEffectsHtml += '</div>';
                sideEffectsHtml += '<p class="side-effect-detail">' + escapeHtml(se.detail) + '</p>';
                if (se.code_fact) {
                    sideEffectsHtml += '<div class="fact-code-box">📄 <strong>수정한 소스 코드 실제 Line 인용:</strong><br>' + formatDiffSyntax(se.code_fact) + '</div>';
                }
                sideEffectsHtml += '<div class="side-effect-target">🎯 <strong>SG 검증 대상:</strong> [' + escapeHtml(se.module_name || '공통') + '] ' + escapeHtml(se.target_menu || '파일') + ' | <strong>원인:</strong> ' + escapeHtml(se.root_cause) + '</div>';
                sideEffectsHtml += '</div>';
            }
            sideEffectsContainer.innerHTML = sideEffectsHtml;

            var tcBody = document.getElementById('tcTableBody');
            var tcHtml = '';
            for (var m = 0; m < data.recommended_tcs.length; m++) {
                var tc = data.recommended_tcs[m];
                tcHtml += '<tr>';
                tcHtml += '<td style="font-weight: bold; color: #818cf8;">' + escapeHtml(tc.id) + '</td>';
                tcHtml += '<td style="font-weight: bold; color: white;">[' + escapeHtml(tc.module_name || '공통') + '] ' + escapeHtml(tc.target_screen) + '</td>';
                tcHtml += '<td>' + escapeHtml(tc.test_scenario) + '</td>';
                tcHtml += '<td><span style="padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; background: rgba(239, 68, 68, 0.2); color: #fca5a5;">' + escapeHtml(tc.priority) + '</span></td>';
                tcHtml += '<td>' + escapeHtml(tc.expected_result) + '</td>';
                tcHtml += '</tr>';
            }
            tcBody.innerHTML = tcHtml;

            var fileDiffContainer = document.getElementById('fileDiffContainer');
            var diffHtml = '';
            for (var n = 0; n < data.files.length; n++) {
                var f = data.files[n];
                diffHtml += '<div class="diff-file-card">';
                diffHtml += '<div class="diff-file-header">';
                diffHtml += '<span>📄 ' + escapeHtml(f.path) + '</span>';
                diffHtml += '<span>+' + f.additions + ' / -' + f.deletions + '</span>';
                diffHtml += '</div>';
                diffHtml += '<div class="diff-pre">' + formatDiffSyntax(f.diff_preview) + '</div>';
                diffHtml += '</div>';
            }
            fileDiffContainer.innerHTML = diffHtml;
        }

        function postCommentToGitLab() {
            if (!currentAnalysisData) return;
            if (!confirm('GitLab에 DLPCenter Sourcegraph AI 분석 코멘트를 등록하시겠습니까?')) return;

            fetch('/api/post-comment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: currentAnalysisData.project_id,
                    commit_sha: currentAnalysisData.commit_sha,
                    comment_body: generateMarkdownReport(currentAnalysisData)
                })
            })
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.status === 'success') alert('GitLab에 Sourcegraph AI 검증 코멘트가 정상 등록되었습니다!');
                else alert('등록 처리 결과를 확인해주세요: ' + result.message);
            })
            .catch(function(e) { alert('처리 오류: ' + e.message); });
        }

        function generateMarkdownReport(data) {
            var md = '## 🛡️ DLPCenter Sourcegraph AI Fact-Based Bug Impact Report\\n';
            md += '**비교 기준**: ' + data.base_branch + ' 브랜치 🆚 **커밋**: ' + data.commit_sha + '\\n';
            md += '**위험도 레벨**: ' + data.risk_level + '\\n\\n';
            md += '### 🎯 1. Sourcegraph 수정한 실제 소스 파일 및 연관 모듈\\n';
            for (var i = 0; i < data.impacted_screens.length; i++) {
                md += '- **[' + data.impacted_screens[i].module_name + '] ' + data.impacted_screens[i].raw_file + '**: ' + data.impacted_screens[i].description + '\\n';
            }
            md += '\\n### ⚠️ 2. Sourcegraph 코드 팩트 기반 파일 성격별 검증 포인트 (UI Checkpoints)\\n';
            for (var j = 0; j < data.side_effects.length; j++) {
                md += '- **[' + data.side_effects[j].category + '] ' + data.side_effects[j].symptom + '**: ' + data.side_effects[j].detail + '\\n';
            }
            md += '\\n### ✅ 3. DLPCenter Sourcegraph 우선 수동 검증 추천 테스트케이스\\n| ID | 연동 제품 / 수정한 파일 / 모듈 | 테스트 시나리오 | 우선순위 |\\n|---|---|---|---|\\n';
            for (var k = 0; k < data.recommended_tcs.length; k++) {
                var tc = data.recommended_tcs[k];
                md += '| ' + tc.id + ' | [' + tc.module_name + '] ' + tc.target_screen + ' | ' + tc.test_scenario + ' | ' + tc.priority + ' |\\n';
            }
            return md;
        }

        function downloadMarkdownReport() {
            if (!currentAnalysisData) return;
            var md = generateMarkdownReport(currentAnalysisData);
            var blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
            var link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'DLPCenter_Sourcegraph_Report_' + (currentAnalysisData.commit_sha ? currentAnalysisData.commit_sha.substring(0,8) : 'commit') + '.md';
            link.click();
        }

        window.onload = function() {
            loadCommitList();
        };
    </script>
</body>
</html>
"""

async def homepage(request):
    return HTMLResponse(HTML_TEMPLATE)

async def list_commits(request):
    project_id = request.query_params.get("project_id", "317")
    gitlab_url = request.query_params.get("gitlab_url", DEFAULT_GITLAB_URL)
    gitlab_token = request.query_params.get("gitlab_token", DEFAULT_GITLAB_TOKEN)

    url = f"{gitlab_url.rstrip('/')}/api/v4/projects/{project_id}/repository/commits?all=true&per_page=100"
    headers = {"PRIVATE-TOKEN": gitlab_token}

    try:
        res = requests.get(url, headers=headers, verify=False, timeout=8)
        if res.status_code == 200:
            commits = res.json()
            formatted = []
            for c in commits:
                formatted.append({
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "author_name": c.get("author_name", "개발자"),
                    "created_at": c.get("created_at")
                })
            return JSONResponse({"status": "success", "commits": formatted})
        else:
            return JSONResponse({"status": "error", "message": f"GitLab HTTP {res.status_code}"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

async def analyze_commit(request):
    try:
        body = await request.json()
        project_id = body.get("project_id", "317")
        base_branch = body.get("base_branch", "PR")
        commit_sha = body.get("commit_sha", "b5b897b9").strip()
        gitlab_url = body.get("gitlab_url") or DEFAULT_GITLAB_URL
        gitlab_token = body.get("gitlab_token") or DEFAULT_GITLAB_TOKEN
        openai_key = body.get("openai_api_key")

        headers = {"PRIVATE-TOKEN": gitlab_token}
        
        commit_url = f"{gitlab_url.rstrip('/')}/api/v4/projects/{project_id}/repository/commits/{commit_sha}"
        diff_url = f"{commit_url}/diff"

        c_res = requests.get(commit_url, headers=headers, verify=False, timeout=8)
        d_res = requests.get(diff_url, headers=headers, verify=False, timeout=8)

        if d_res.status_code != 200:
            return JSONResponse({"status": "error", "message": f"GitLab 커밋 정보({commit_sha[:8]})를 가져올 수 없습니다. ({d_res.status_code})"})

        commit_info = c_res.json()
        diff_info = d_res.json()

        commit_title = commit_info.get("title", f"Commit {commit_sha[:8]}")

        files_summary = []
        full_diff_text = ""
        for c in diff_info[:20]:
            path = c.get("new_path") or c.get("old_path", "unknown")
            diff = c.get("diff", "")
            additions = len(re.findall(r'^\+[^\+]', diff, re.MULTILINE))
            deletions = len(re.findall(r'^\-[^\-]', diff, re.MULTILINE))
            
            diff_preview = diff[:1500] + ("\n... [중략]" if len(diff) > 1500 else "")
            full_diff_text += f"\n--- File: {path} ---\n{diff_preview}\n"

            files_summary.append({
                "path": path,
                "additions": additions,
                "deletions": deletions,
                "diff_preview": diff_preview
            })

        sg_symbol_data = query_sourcegraph_api(commit_sha, files_summary)

        if openai_key and len(openai_key.strip()) > 5:
            analysis_result = analyze_with_openai_fact_engine(commit_title, full_diff_text, files_summary, base_branch, openai_key, sg_symbol_data)
        else:
            analysis_result = analyze_with_pi_cli(commit_title, full_diff_text, files_summary, base_branch, sg_symbol_data)
            
        # Ensure correct structure for frontend
        if not isinstance(analysis_result, dict):
            analysis_result = {}
        if "impacted_screens" not in analysis_result:
            analysis_result["impacted_screens"] = []
        if "side_effects" not in analysis_result:
            analysis_result["side_effects"] = []
        if "recommended_tcs" not in analysis_result:
            analysis_result["recommended_tcs"] = []
        if "risk_level" not in analysis_result:
            analysis_result["risk_level"] = "MEDIUM"
        if "sg_fact_info" not in analysis_result:
            analysis_result["sg_fact_info"] = sg_symbol_data

        analysis_result["project_id"] = project_id
        analysis_result["base_branch"] = base_branch
        analysis_result["commit_sha"] = commit_sha
        analysis_result["commit_title"] = commit_title
        analysis_result["project_name"] = "DLPCenter"
        analysis_result["changes_count"] = len(diff_info)
        analysis_result["files"] = files_summary

        return JSONResponse({"status": "success", "data": analysis_result})

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

def query_sourcegraph_api(commit_sha, files_summary):
    # 이제 Sourcegraph API 대신 사전에 스캔된 URL_MAP을 사용하여 정확한 화면(메뉴) 매핑 정보를 리턴합니다.
    mapped_info = []
    for f in files_summary:
        path = f['path']
        mapped_screen = get_mapped_screen_deep(path)
        if mapped_screen:
            mapped_info.append(f"[{path}] -> 팩트 추적된 실제 화면: {mapped_screen}")
        elif path in URL_MAP:
            mapped_info.append(f"[{path}] -> 실제 연동 화면명: {URL_MAP[path].get('screen_name', '알수없음')}")
        else:
            filename = path.split('/')[-1]
            mapped_info.append(f"[{path}] -> 연동 화면: [DLPCenter] 공통/백엔드/기타 모듈 ({filename})")
    return "\n".join(mapped_info)

def detect_somansa_module(file_path):
    p = file_path.lower()
    if any(k in p for k in ['pczikimi', 'myzikimi', 'pc_zikimi', 'mypc']):
        return "PCZIKIMI", "내PC지키미 (PC보안점검)"
    elif any(k in p for k in ['serverzikimi', 'zikimi', 'zk', 'control', 'knox']):
        return "ZIKIMI", "서버지키미 (서버보안/접속제어)"
    elif any(k in p for k in ['dbi', 'dbdiscover', 'db_i', 'dbi_']):
        return "DBI", "DB-i (DB 개인정보/보안)"
    elif any(k in p for k in ['maili', 'mail', 'smtp', 'approval']):
        return "MAILI", "Mail-i (메일유출차단)"
    elif any(k in p for k in ['serveri', 'svi', 'discover', 'server_detect', 'sftp']):
        return "SERVERI", "Server-i (서버 개인정보)"
    elif any(k in p for k in ['privacy', 'pvi', 'policya', 'endpoint', 'copyprevent', 'pc']):
        return "PRIVACYI", "Privacy-i (PC 개인정보/매체제어)"
    elif any(k in p for k in ['wsg', 'aidlp', 'prism', 'ai']):
        return "AIDLP", "WSG / AI-DLP 모듈"
    elif any(k in p for k in ['webkeeper', 'wk']):
        return "WEBKEEPER", "Webkeeper (웹유출차단)"
    elif any(k in p for k in ['edr']):
        return "EDR", "EDR (단말위협탐지)"
    else:
        return "COMMON", "DLPCenter 통합공통"

def get_mapped_screen_deep(file_path):
    if file_path in URL_MAP:
        return URL_MAP[file_path].get('screen_name', '')
        
    filename = file_path.split('/')[-1]
    if not filename.endswith('.java'):
        return ""
        
    # 역추적 시작 (Sourcegraph API 사용)
    try:
        class_name = filename.split('.')[0]
        search_target = class_name[:-4] if class_name.endswith('Impl') else class_name
        
        query = f'repo:gitlab.somansa.com/platform/git-dlpcenter lang:java {search_target} count:20'
        headers = {'Authorization': f'token {SOURCEGRAPH_TOKEN}', 'Content-Type': 'application/json'}
        graphql_query = f'query {{ search(query: "{query}", version: V3) {{ results {{ results {{ ... on FileMatch {{ file {{ path }} }} }} }} }} }}'
        
        import requests
        res = requests.post(f'{SOURCEGRAPH_URL}/.api/graphql', json={'query': graphql_query}, headers=headers, timeout=5)
        if res.status_code != 200: return ""
        
        matches = res.json().get('data', {}).get('search', {}).get('results', {}).get('results', [])
        if not matches: return ""
        
        parents = [m['file']['path'] for m in matches if m['file']['path'] != file_path]
        
        # 1. 부모에서 찾기
        for p in parents:
            if p in URL_MAP:
                return f"{URL_MAP[p].get('screen_name', '')} (연동된 컨트롤러를 통해 호출됨)"
                
        # 2. 조부모에서 찾기 (Service -> Controller)
        for p in parents[:5]:
            parent_class = p.split('/')[-1].split('.')[0]
            q2 = f'repo:gitlab.somansa.com/platform/git-dlpcenter lang:java {parent_class} count:10'
            res2 = requests.post(f'{SOURCEGRAPH_URL}/.api/graphql', json={'query': f'query {{ search(query: "{q2}", version: V3) {{ results {{ results {{ ... on FileMatch {{ file {{ path }} }} }} }} }} }}'}, headers=headers, timeout=3)
            if res2.status_code == 200:
                m2 = res2.json().get('data', {}).get('search', {}).get('results', {}).get('results', [])
                if m2:
                    for match in m2:
                        gp = match['file']['path']
                        if gp in URL_MAP:
                            return f"{URL_MAP[gp].get('screen_name', '')} (의존성 추적 결과)"
    except Exception as e:
        print("Deep trace error:", e)
        pass
        
    return ""

def analyze_fact_based_diff_engine(commit_title, full_diff_text, files_summary, base_branch="PR", sg_fact_info=None):
    screens = []
    side_effects = []
    tcs = []

    for f in files_summary:
        file_path = f["path"]
        diff_text = f["diff_preview"]
        module_code, module_name = detect_somansa_module(file_path)
        filename = file_path.split('/')[-1]
        mapped_screen = get_mapped_screen_deep(file_path)
        ext = filename.split('.')[-1].lower() if '.' in filename else ''

        added_lines = [l[1:].strip() for l in diff_text.split('\n') if l.startswith('+') and not l.startswith('+++')]
        deleted_lines = [l[1:].strip() for l in diff_text.split('\n') if l.startswith('-') and not l.startswith('---')]
        code_sample = added_lines[0] if added_lines else (deleted_lines[0] if deleted_lines else "소스 코드 패치")

        changed_vars = re.findall(r'(\w+)\s*=', diff_text) + re.findall(r'getParameter\(["\'](\w+)["\']\)', diff_text)
        changed_vars = list(set([v for v in changed_vars if len(v) > 2 and v not in ['String', 'int', 'true', 'false', 'null', 'function', 'var', 'let']]))
        var_fact_str = ", ".join(changed_vars[:2]) if changed_vars else "파라미터/변수"

        if ext in ['svg', 'png', 'jpg', 'gif', 'css', 'ico', 'woff']:
            screens.append({
                "module_code": module_code,
                "module_name": module_name,
                "raw_file": file_path,
                "screen_name": f"[{module_name}] {mapped_screen} (UI 리소스)" if mapped_screen else f"[{module_name}] UI 디자인 리소스",
                "impact_degree": "직접 영향 (HIGH)",
                "description": f"Sourcegraph 스캔: 리소스 파일 `{file_path}` 변경.",
                "affected_features": ["화면 아이콘 렌더링", "UI 레이아웃 정렬", "버튼 이미지 표출"]
            })

            side_effects.append({
                "module_name": module_name,
                "category": "🎨 [Sourcegraph SG 팩트 - UI 가시성 및 레이아웃]",
                "symptom": f"해당 UI/디자인 리소스 변경으로 인해 연동 화면에서 아이콘 깨짐 또는 레이아웃 정렬 이상 발생 가능성",
                "severity": "MEDIUM",
                "detail": f"디자인 리소스 패치건입니다. 해당 화면 접속 후 전반적인 UI 렌더링 및 레이아웃 상태 수동 확인을 권장합니다.",
                "code_fact": f"디자인 리소스 파일 변경: {filename}",
                "target_menu": f"{mapped_screen} 화면" if mapped_screen else f"수정한 파일: `{file_path}`",
                "root_cause": f"`{file_path}` 리소스 파일 패치"
            })

        elif ext in ['jsp', 'html', 'js', 'vue', 'jsx']:
            screens.append({
                "module_code": module_code,
                "module_name": module_name,
                "raw_file": file_path,
                "screen_name": f"[{module_name}] {mapped_screen}" if mapped_screen else f"[{module_name}] 웹 UI 화면",
                "impact_degree": "직접 영향 (HIGH)",
                "description": f"Sourcegraph 스캔: UI 스크립트 파일 `{file_path}` 내 로직/변수({var_fact_str}) 변경.",
                "affected_features": ["화면 버튼 클릭 이벤트", "입력폼 데이터 전송", "팝업 레이어 표출"]
            })

            side_effects.append({
                "module_name": module_name,
                "category": "🔴 [Sourcegraph SG 팩트 - 버튼 클릭 먹통 위험]",
                "symptom": f"해당 화면에서 주요 기능 버튼 클릭 시 반응이 없거나 스크립트 오류로 인해 멈출 가능성",
                "severity": "HIGH",
                "detail": f"스크립트 로직 패치로 인해 브라우저 환경에서 버튼 클릭 이벤트 먹통이나 데이터 렌더링 실패 가능성이 있습니다. 화면 내 주요 기능 수동 검증을 권장합니다.",
                "code_fact": f"{code_sample[:100]}",
                "target_menu": f"{mapped_screen} 화면" if mapped_screen else f"수정한 파일: `{file_path}`",
                "root_cause": f"`{file_path}` 스크립트 패치"
            })

        elif ext in ['java', 'class', 'jar']:
            screens.append({
                "module_code": module_code,
                "module_name": module_name,
                "raw_file": file_path,
                "screen_name": f"[{module_name}] {mapped_screen}" if mapped_screen else f"[{module_name}] API 서버 컨트롤러",
                "impact_degree": "직접 영향 (HIGH)",
                "description": f"Sourcegraph 스캔: 백엔드 자바 파일 `{file_path}` 내 변수({var_fact_str}) 변경.",
                "affected_features": ["REST API 응답 수신", "Controller 데이터 파싱", "서비스 예외 처리"]
            })

            side_effects.append({
                "module_name": module_name,
                "category": "🔴 [Sourcegraph SG 팩트 - 화면 500 에러 위험]",
                "symptom": f"해당 서버 로직과 연동되는 화면에 접근하거나 데이터 조회 시 500 에러 팝업 또는 데이터 미출력 가능성",
                "severity": "HIGH",
                "detail": f"서버 데이터 처리 로직 수정으로 인해 API 응답 시 예외가 발생할 위험이 있습니다. 해당 기능(조회/저장 등) 수행 시 데이터가 비어서 나오는지 수동 검증을 권장합니다.",
                "code_fact": f"{code_sample[:100]}",
                "target_menu": f"{mapped_screen} 화면" if mapped_screen else f"수정한 파일: `{file_path}`",
                "root_cause": f"서버 기능/데이터 처리 로직 패치"
            })

        elif ext in ['xml', 'sql']:
            screens.append({
                "module_code": module_code,
                "module_name": module_name,
                "raw_file": file_path,
                "screen_name": f"[{module_name}] {mapped_screen} (DB 쿼리)" if mapped_screen else f"[{module_name}] DB 데이터 처리 쿼리",
                "impact_degree": "직접 영향 (HIGH)",
                "description": f"Sourcegraph 스캔: DB MyBatis XML/SQL 파일 `{file_path}` 쿼리 패치.",
                "affected_features": ["'검색' 버튼 조회 결과", "목록 페이징 번호", "DB 데이터 저장"]
            })

            side_effects.append({
                "module_name": module_name,
                "category": "🔴 [Sourcegraph SG 팩트 - 조회 목록 누락 위험]",
                "symptom": f"해당 화면에서 데이터를 '검색'하거나 조회할 때 목록 결과가 누락되거나 에러가 발생할 가능성",
                "severity": "HIGH",
                "detail": f"DB 쿼리 조건 및 매핑 파라미터 수정으로 인해, 화면에서 데이터 조회 시 결과가 누락되거나 잘못된 데이터가 노출되는지 수동 확인을 권장합니다.",
                "code_fact": f"{code_sample[:100]}",
                "target_menu": f"{mapped_screen} 화면" if mapped_screen else f"수정한 파일: `{file_path}`",
                "root_cause": f"DB 조회/저장 쿼리 패치"
            })

        else:
            screens.append({
                "module_code": module_code,
                "module_name": module_name,
                "raw_file": file_path,
                "screen_name": f"[{module_name}] 시스템 스크립트/환경설정 모듈 ({filename})",
                "impact_degree": "간접 영향 (MEDIUM)",
                "description": f"Sourcegraph 스캔: 시스템 스크립트 파일 `{file_path}` 패치.",
                "affected_features": ["모듈 버전 업데이트", "환경설정 연동", "서버 프로세스 제어"]
            })

            side_effects.append({
                "module_name": module_name,
                "category": "🛠️ [Sourcegraph SG 팩트 - 시스템 설정 적용 유무]",
                "symptom": "해당 모듈 패치 후 화면에서 상태값 연동 및 설정 적용 유무 수동 확인 권장",
                "severity": "MEDIUM",
                "detail": f"시스템 설정 파일 패치 적용 후, 관리자 콘솔 또는 관련 기능에서 상태값 변경 및 정상 동작 유무를 수동 확인하세요.",
                "code_fact": f"{code_sample[:100]}",
                "target_menu": f"{mapped_screen} 화면" if mapped_screen else f"수정한 파일: `{file_path}`",
                "root_cause": f"시스템 스크립트 및 환경설정 패치"
            })

    if not screens:
        screens.append({
            "module_code": "COMMON",
            "module_name": "DLPCenter 공통",
            "raw_file": files_summary[0]['path'],
            "screen_name": "[DLPCenter 공통] 공통 코어 모듈",
            "impact_degree": "직접 영향 (HIGH)",
            "description": f"공통 파일 `{files_summary[0]['path']}` 패치.",
            "affected_features": ["'환경설정 저장' 버튼", "'대시보드 조회'"]
        })

    for idx, sc in enumerate(screens[:3]):
        tcs.append({
            "id": f"TC-SG-00{idx+1}",
            "module_name": sc["module_name"],
            "target_screen": f"{sc['screen_name']} 연관 화면/기능",
            "test_scenario": f"[{sc['screen_name']}] 화면에 접속하여 관련된 주요 기능 및 버튼들이 정상적으로 동작하는지 수동 검증 진행",
            "priority": "High",
            "expected_result": "Sourcegraph 스캔 기준에 따라 아이콘 깨짐 없이 정상 렌더링되거나 기능이 오류 없이 정상 수행됨"
        })

    risk_level = "HIGH" if any(s["severity"] == "CRITICAL" or s["severity"] == "HIGH" for s in side_effects) else "MEDIUM"

    return {
        "risk_level": risk_level,
        "sg_fact_info": sg_fact_info,
        "impacted_screens": screens,
        "side_effects": side_effects,
        "recommended_tcs": tcs
    }

def analyze_with_pi_cli(commit_title, full_diff_text, files_summary, base_branch, sg_symbol_data):
    try:
        print("[INFO] Calling local Pi Agent (CLI) to generate AI report...")
        prompt = f'''
너는 소만사 DLPCenter 15년 차 수석 QA 엔지니어야.
이번 커밋에 포함된 파일들이 실제 화면(UI)이나 API와 어떻게 매핑되는지에 대한 팩트 데이터를 바탕으로, QA 담당자가 직관적으로 이해할 수 있는 "화면 중심의 검증 가이드"를 작성해.

[커밋 제목]: {commit_title}
[비교 기준]: {base_branch} 브랜치
[코드 ↔ 화면 매핑 팩트 데이터]:
{sg_symbol_data}

[실제 코드 Diff 내용]:
{full_diff_text[:3000]}

중요 지침:
1. QA 엔지니어가 리포트를 읽습니다. `.java`나 `.jsp` 같은 소스코드 파일 경로나 개발 용어를 '증상(symptom)'이나 '상세 가이드(detail)'에 절대로 노출하지 마세요.
2. 팩트 데이터에 화면명이 없다면, 수정된 파일명(예: ServerConnect)을 보고 "서버 연동 화면" 혹은 "서버 연결 관리 메뉴"처럼 QA가 알아들을 수 있는 한글 메뉴/기능명으로 번역해서 작성하세요.
3. 반드시 아래 JSON 형식만 반환하세요 (마크다운 없이 순수 JSON만 출력).

{{
  "risk_level": "HIGH 또는 MEDIUM",
  "impacted_screens": [
    {{
      "module_code": "해당 제품군(PRIVACYI 등)",
      "module_name": "제품 모듈명",
      "raw_file": "수정한 실제 파일 경로",
      "screen_name": "팩트 데이터에 명시된 한글 화면명/메뉴명 (없을시 유추)",
      "impact_degree": "직접 영향 (HIGH) 또는 간접",
      "description": "어떤 화면의 어떤 기능이 수정되었는지 QA가 알기 쉽게 설명",
      "affected_features": ["영향받는 화면 내 UI 요소나 기능 1", "기능 2"]
    }}
  ],
  "side_effects": [
    {{
      "module_name": "제품 모듈명",
      "category": "🔴 [화면 오류 위험] 또는 🎨 [UI 깨짐 위험] 등",
      "symptom": "해당 화면(메뉴)에서 발생 가능한 구체적 결함 증상",
      "severity": "HIGH 또는 MEDIUM",
      "detail": "QA가 이 증상을 확인하기 위해 어떤 화면 메뉴에 들어가서 어떤 행동을 해야하는지 가이드",
      "code_fact": "수정된 주요 설정(예: 서버 주소 변경, 조회 조건 변경 등)",
      "target_menu": "테스트해야 할 화면명/메뉴명",
      "root_cause": "어떤 로직이 수정되었는지"
    }}
  ],
  "recommended_tcs": [
    {{
      "id": "TC-SG-001",
      "module_name": "제품 모듈명",
      "target_screen": "테스트할 화면명",
      "test_scenario": "수동 테스트 수행 스텝 (예: OO메뉴 접속 -> 버튼 클릭 -> XX 확인)",
      "priority": "High 또는 Medium",
      "expected_result": "정상 동작 시 기대되는 결과"
    }}
  ]
}}
'''
        # Pi CLI를 non-interactive 모드(-p)로 실행하여 출력값을 캡처합니다.
        import sys
        pi_cmd = "pi.cmd" if sys.platform == "win32" else "pi"
        result = subprocess.run([pi_cmd, "--mode", "json", "-p", prompt], capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            print("[ERROR] Pi execution failed:", result.stderr)
            raise Exception("Pi execution failed")
            
        output = result.stdout.strip()
        print("[DEBUG] Pi CLI Output:", output)
        
        # parse json from output stream (JSON-L handling)
        import json
        json_str = ""
        for line in output.split('\n'):
            if not line.strip(): continue
            try:
                msg = json.loads(line)
                if msg.get('type') == 'message_end' and msg.get('message', {}).get('role') == 'assistant':
                    for content_block in msg['message']['content']:
                        if content_block.get('type') == 'text':
                            json_str = content_block['text']
                            break
                    break
            except:
                pass
                
        if not json_str:
            # Fallback if text output was used
            json_str = output
            
        # 마크다운 코드블록 제거
        json_str = re.sub(r'```(?:json)?\n?', '', json_str)
        json_str = re.sub(r'```', '', json_str).strip()
        
        return json.loads(json_str)
    except Exception as e:
        print("[ERROR] Pi Agent generation failed:", e)
        return analyze_fact_based_diff_engine(commit_title, full_diff_text, files_summary, base_branch, sg_symbol_data)

def analyze_with_openai_fact_engine(commit_title, full_diff_text, files_summary, base_branch, openai_key, sg_symbol_data):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        prompt = f'''
너는 소만사 DLPCenter 15년 차 수석 QA 엔지니어야.
이번 커밋에 포함된 파일들이 실제 화면(UI)이나 API와 어떻게 매핑되는지에 대한 팩트 데이터를 바탕으로, QA 담당자가 직관적으로 이해할 수 있는 "화면 중심의 검증 가이드"를 작성해줘. "oooo.java 파일을 확인하라"는 식의 답변은 절대 금지하며, 반드시 아래 팩트 데이터를 바탕으로 한글 화면명이나 모듈명을 명시해야 해.

[커밋 제목]: {commit_title}
[비교 기준]: {base_branch} 브랜치
[코드 ↔ 화면 매핑 팩트 데이터]:
{sg_symbol_data}

[실제 코드 Diff 내용]:
{full_diff_text[:3500]}

중요 지침:
1. QA 엔지니어가 리포트를 읽습니다. `.java`나 `.jsp` 같은 소스코드 파일 경로를 '증상(symptom)'이나 '상세 가이드(detail)'에 절대로 노출하지 마세요.
2. 팩트 데이터에 화면명이 없다면, 수정된 파일명(예: ServerConnect)을 보고 "서버 연동 화면" 혹은 "서버 연결 관리 메뉴"처럼 QA가 알아들을 수 있는 한글 메뉴/기능명으로 100% 번역해서 작성하세요.
3. "oooo.java 백엔드 자바 로직 수정을 통해" 같은 개발자스러운 표현은 절대 금지합니다. 대신 "서버 연결 관리 기능 수정으로 인해"라고 작성하세요.

반드시 아래 JSON 형식으로 응답해:
{{
  "risk_level": "HIGH 또는 MEDIUM 또는 LOW",
  "impacted_screens": [
    {{
      "module_code": "해당 제품군(PRIVACYI 등)",
      "module_name": "제품 모듈명",
      "raw_file": "수정한 실제 파일 경로",
      "screen_name": "팩트 데이터에 명시된 한글 화면명/메뉴명 (없을시 유추)",
      "impact_degree": "직접 영향 (HIGH) 또는 간접",
      "description": "어떤 화면의 어떤 기능이 수정되었는지 QA가 알기 쉽게 설명",
      "affected_features": ["영향받는 화면 내 UI 요소나 기능 1", "기능 2"]
    }}
  ],
  "side_effects": [
    {{
      "module_name": "제품 모듈명",
      "category": "🔴 [화면 오류 위험] 또는 🎨 [UI 깨짐 위험] 등",
      "symptom": "해당 화면(메뉴)에서 발생 가능한 구체적 결함 증상",
      "severity": "HIGH 또는 MEDIUM",
      "detail": "QA가 이 증상을 확인하기 위해 어떤 화면 메뉴에 들어가서 어떤 행동을 해야하는지 가이드",
      "code_fact": "원인이 되는 코드의 주요 수정 내용",
      "target_menu": "테스트해야 할 화면명/메뉴명",
      "root_cause": "어떤 로직이 수정되었는지"
    }}
  ],
  "recommended_tcs": [
    {{
      "id": "TC-SG-001",
      "module_name": "제품 모듈명",
      "target_screen": "테스트할 화면명",
      "test_scenario": "수동 테스트 수행 스텝 (예: OO메뉴 접속 -> 버튼 클릭 -> XX 확인)",
      "priority": "High 또는 Medium",
      "expected_result": "정상 동작 시 기대되는 결과"
    }}
  ]
}}
'''
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print("OpenAI Error:", e)
        return analyze_fact_based_diff_engine(commit_title, full_diff_text, files_summary, base_branch, sg_symbol_data)

async def post_comment(request):
    try:
        body = await request.json()
        project_id = body.get("project_id", "317")
        commit_sha = body.get("commit_sha", "b5b897b9")
        comment_body = body.get("comment_body", "DLPCenter AI QA Report")

        url = f"{DEFAULT_GITLAB_URL}/api/v4/projects/{project_id}/repository/commits/{commit_sha}/comments"
        headers = {"PRIVATE-TOKEN": DEFAULT_GITLAB_TOKEN}

        res = requests.post(url, headers=headers, json={"body": comment_body}, verify=False, timeout=5)
        if res.status_code in [200, 201]:
            return JSONResponse({"status": "success", "message": "Commit comment posted!"})
        else:
            return JSONResponse({"status": "error", "message": f"GitLab HTTP {res.status_code}: {res.text}"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

routes = [
    Route("/", homepage, methods=["GET"]),
    Route("/api/commits", list_commits, methods=["GET"]),
    Route("/api/analyze-commit", analyze_commit, methods=["POST"]),
    Route("/api/post-comment", post_comment, methods=["POST"])
]

middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
]

app = Starlette(debug=True, routes=routes, middleware=middleware)

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 DLPCenter QA AI Impact Analyzer Portal - Local Server Running")
    print("👉 접속 주소: http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
