from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import (
    get_dashboard_summary, 
    get_stats, 
    get_leads_elite, 
    get_groups_elite, 
    get_conversations_elite,
    get_conversions_elite,
    get_reseller_prospects_elite
)

router = APIRouter()

@router.get("/stats")
def stats_endpoint(db: Session = Depends(get_db)):
    """Elite Module 12: GET /stats"""
    return get_stats(db)

@router.get("/leads")
def leads_endpoint(db: Session = Depends(get_db)):
    """Elite Module 12: GET /leads"""
    return get_leads_elite(db)

@router.get("/groups")
def groups_endpoint(db: Session = Depends(get_db)):
    """Elite Module 12: GET /groups"""
    return get_groups_elite(db)

@router.get("/conversions")
def conversions_endpoint(db: Session = Depends(get_db)):
    """Elite Module 12: GET /conversions"""
    return get_conversions_elite(db)

@router.get("/reseller-prospects")
def reseller_prospects_endpoint(db: Session = Depends(get_db)):
    """Elite Module 16: GET /reseller-prospects"""
    return get_reseller_prospects_elite(db)

@router.get("/conversations")
def conversations_endpoint(db: Session = Depends(get_db)):
    return get_conversations_elite(db)

@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary_endpoint(db: Session = Depends(get_db)) -> DashboardSummary:
    return get_dashboard_summary(db)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    return """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SLIE Elite | Ultimate Intelligence Command</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        elite: {
                            50: '#f0f4ff', 100: '#e0e8ff', 200: '#c1d1ff', 300: '#92afff',
                            400: '#5c83ff', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
                            800: '#1e40af', 900: '#1e3a8a', 950: '#000000',
                        },
                        surface: {
                            800: '#121212', 900: '#0a0a0a', 950: '#000000',
                        }
                    },
                    fontFamily: { sans: ['Plus Jakarta Sans', 'sans-serif'] },
                }
            }
        }
    </script>
    <style>
        body {
            background-color: #000000;
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.05) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(37, 99, 235, 0.03) 0px, transparent 50%);
            min-height: 100vh;
        }
        .glass-card {
            background: #0d0d0d;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 24px 0 rgba(0, 0, 0, 0.6);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .glass-card:hover {
            border-color: rgba(59, 130, 246, 0.4);
            background: #141414;
            transform: translateY(-4px) scale(1.01);
            box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.8);
        }
        .sidebar-active {
            background: rgba(59, 130, 246, 0.1);
            border-left: 4px solid #3b82f6;
            color: #fff;
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(59, 130, 246, 0.3); border-radius: 10px; }
        .live-dot {
            width: 8px; height: 8px; background: #10b981;
            border-radius: 50%; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse-dot 2s infinite;
        }
        @keyframes pulse-dot {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        .stat-glow { filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.2)); }
        @media (max-width: 1024px) {
            .sidebar-open aside { transform: translateX(0); }
            .sidebar-open .backdrop { display: block; }
        }
    </style>
</head>
<body class="text-slate-200 antialiased overflow-x-hidden flex flex-col lg:flex-row min-h-screen">
    <div id="backdrop" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 hidden lg:hidden" onclick="toggleSidebar()"></div>

    <!-- Sidebar -->
    <aside id="sidebar" class="fixed inset-y-0 left-0 z-50 w-72 bg-surface-950/95 border-r border-white/5 transform -translate-x-full lg:translate-x-0 transition-transform duration-300 ease-out lg:static lg:block flex flex-col shadow-2xl">
        <div class="p-8 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-elite-600 rounded-xl flex items-center justify-center shadow-lg shadow-elite-500/30">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                </div>
                <div class="flex flex-col">
                    <span class="text-lg font-bold tracking-tight text-white leading-none">SLIE <span class="text-elite-500">ELITE</span></span>
                    <span class="text-[9px] font-bold text-slate-500 tracking-[0.2em] uppercase mt-1">Intelligence v4.0</span>
                </div>
            </div>
            <button class="lg:hidden p-2 text-slate-400" onclick="toggleSidebar()">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
        </div>
        
        <nav class="flex-1 px-4 py-2 space-y-1.5 overflow-y-auto">
            <div class="px-4 py-2 text-[10px] font-bold text-slate-600 uppercase tracking-[0.2em]">Core Operations</div>
            <a href="#" class="flex items-center gap-3 px-4 py-3 rounded-xl sidebar-active text-sm font-semibold transition-all group">
                <svg class="w-5 h-5 text-elite-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
                Command Center
            </a>
            <a href="#" class="flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 text-sm font-semibold transition-all">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                Lead Intelligence
            </a>
            <a href="#" class="flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 text-sm font-semibold transition-all">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                Conversations
            </a>
            <div class="px-4 py-4 mt-4 text-[10px] font-bold text-slate-600 uppercase tracking-[0.2em]">Safety & Scale</div>
            <a href="#" class="flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 text-sm font-semibold transition-all">
                <svg class="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                Human Engine
            </a>
            <a href="#" class="flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 text-sm font-semibold transition-all">
                <svg class="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>
                System Config
            </a>
        </nav>

        <div class="p-6 border-t border-white/5">
            <div class="bg-slate-900/80 rounded-2xl p-4 border border-white/5 shadow-inner">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <div class="live-dot"></div>
                        <span class="text-[9px] font-bold text-emerald-500 uppercase tracking-widest">Active Node</span>
                    </div>
                    <span class="text-[9px] font-bold text-slate-500 uppercase">100% Secure</span>
                </div>
                <div class="w-full bg-slate-800 rounded-full h-1.5 mb-2 overflow-hidden">
                    <div class="bg-emerald-500 h-full w-[85%] rounded-full shadow-[0_0_8px_rgba(16,185,129,0.4)]"></div>
                </div>
                <p class="text-[9px] text-slate-500 leading-relaxed font-medium">Account trust score is optimal. No risk detected.</p>
            </div>
        </div>
    </aside>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col min-w-0 bg-transparent relative">
        <!-- Header -->
        <header class="h-20 flex items-center justify-between px-6 lg:px-10 sticky top-0 z-30 bg-surface-950/60 backdrop-blur-xl border-b border-white/5">
            <div class="flex items-center gap-4">
                <button class="lg:hidden p-3 bg-white/5 rounded-xl text-slate-400 hover:text-white transition-colors" onclick="toggleSidebar()">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
                </button>
                <div class="flex flex-col">
                    <h2 class="text-sm font-bold text-white uppercase tracking-[0.2em] flex items-center gap-2">
                        Overview Center
                        <span class="w-1 h-1 bg-slate-600 rounded-full"></span>
                        <span id="last-updated" class="text-slate-500 font-medium tabular-nums lowercase tracking-normal">syncing...</span>
                    </h2>
                </div>
            </div>
            <div class="flex items-center gap-5">
                <div class="hidden md:flex flex-col items-end">
                    <span class="text-[10px] font-bold text-white">System Admin</span>
                    <span class="text-[9px] font-bold text-emerald-500 uppercase tracking-widest">Master Control</span>
                </div>
                <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-elite-600 to-elite-800 p-[1px] shadow-lg shadow-elite-500/20">
                    <div class="w-full h-full bg-surface-950 rounded-[11px] flex items-center justify-center font-bold text-xs text-white">SA</div>
                </div>
            </div>
        </header>

        <main class="p-6 lg:p-10 space-y-10 max-w-[1600px] mx-auto w-full">
            <!-- KPI Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <div class="glass-card rounded-3xl p-7 transition-all group overflow-hidden relative">
                    <div class="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                        <svg class="w-16 h-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                    </div>
                    <div class="text-slate-500 text-[10px] font-bold uppercase tracking-widest mb-2">Leads Detected</div>
                    <div class="flex items-end justify-between relative z-10">
                        <div class="text-4xl font-extrabold text-white tracking-tight stat-glow" id="stat-leads">0</div>
                        <div class="text-[10px] font-bold text-emerald-500 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20 shadow-sm">+12%</div>
                    </div>
                </div>
                <div class="glass-card rounded-3xl p-7 transition-all group overflow-hidden relative border-l-4 border-purple-500/50">
                    <div class="text-slate-500 text-[10px] font-bold uppercase tracking-widest mb-2">Conv. Rate</div>
                    <div class="flex items-end justify-between relative z-10">
                        <div class="text-4xl font-extrabold text-white tracking-tight" id="stat-conv-rate">0%</div>
                        <div class="text-[10px] font-bold text-purple-400 bg-purple-400/10 px-2.5 py-1 rounded-lg border border-purple-400/20">Target: 25%</div>
                    </div>
                </div>
                <div class="glass-card rounded-3xl p-7 transition-all group overflow-hidden relative">
                    <div class="text-slate-500 text-[10px] font-bold uppercase tracking-widest mb-2">Analyzed Msg</div>
                    <div class="flex items-end justify-between relative z-10">
                        <div class="text-4xl font-extrabold text-white tracking-tight" id="stat-messages">0</div>
                        <div class="text-[10px] font-bold text-blue-400 bg-blue-400/10 px-2.5 py-1 rounded-lg border border-blue-400/20">Real-time</div>
                    </div>
                </div>
                <div class="glass-card rounded-3xl p-7 transition-all group overflow-hidden relative">
                    <div class="text-slate-500 text-[10px] font-bold uppercase tracking-widest mb-2">Total Groups</div>
                    <div class="flex items-end justify-between relative z-10">
                        <div class="text-4xl font-extrabold text-white tracking-tight" id="stat-groups">0</div>
                        <div class="text-[10px] font-bold text-amber-400 bg-amber-400/10 px-2.5 py-1 rounded-lg border border-amber-400/20">Scale</div>
                    </div>
                </div>
            </div>

            <!-- Charts Row -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-10">
                <div class="lg:col-span-2 glass-card rounded-[2.5rem] p-8 lg:p-10">
                    <div class="flex items-center justify-between mb-10">
                        <div class="flex flex-col">
                            <h3 class="font-bold text-xl text-white">Community Influence</h3>
                            <p class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-1">Cross-Group Authority Analysis</p>
                        </div>
                        <div class="flex gap-2">
                            <span class="text-[9px] font-bold text-elite-400 bg-elite-400/10 px-3 py-1.5 rounded-xl border border-elite-400/20">LIVE DATA</span>
                        </div>
                    </div>
                    <div class="h-[300px] w-full"><canvas id="influenceChart"></canvas></div>
                </div>
                <div class="glass-card rounded-[2.5rem] p-8 lg:p-10 flex flex-col">
                    <div class="flex flex-col mb-10">
                        <h3 class="font-bold text-xl text-white">LTV Segments</h3>
                        <p class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-1">Lead Lifetime Value Distribution</p>
                    </div>
                    <div class="h-[300px] w-full flex-1"><canvas id="ltvChart"></canvas></div>
                </div>
            </div>

            <!-- Activity & Health -->
            <div class="grid grid-cols-1 xl:grid-cols-12 gap-10">
                <!-- Live Stream -->
                <div class="xl:col-span-8 glass-card rounded-[2.5rem] overflow-hidden flex flex-col border-t-2 border-elite-500/20">
                    <div class="p-8 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                        <h3 class="font-bold text-lg text-white flex items-center gap-3">
                            <span class="live-dot"></span>
                            Intelligence Stream
                        </h3>
                        <div class="flex items-center gap-3">
                            <span class="text-[9px] text-slate-500 font-bold uppercase tracking-widest">Auto-refreshes every 5s</span>
                            <div class="w-px h-4 bg-white/5"></div>
                            <button class="text-[9px] font-bold text-elite-500 uppercase hover:text-elite-400 transition-colors">Clear Log</button>
                        </div>
                    </div>
                    <div id="activity-log" class="divide-y divide-white/5 max-h-[600px] overflow-y-auto">
                        <!-- Activity items -->
                    </div>
                    <div class="p-4 bg-white/[0.01] border-t border-white/5 text-center">
                        <button class="text-[10px] font-bold text-slate-500 uppercase tracking-widest hover:text-white transition-colors">View All Activities</button>
                    </div>
                </div>

                <!-- Account Health & Quick Info -->
                <div class="xl:col-span-4 space-y-10">
                    <div class="glass-card rounded-[2.5rem] p-8">
                        <div class="flex items-center justify-between mb-8">
                            <h3 class="font-bold text-lg text-white">Safety Tracker</h3>
                            <svg class="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                        </div>
                        <div id="account-health" class="space-y-8">
                            <!-- Account health -->
                        </div>
                    </div>
                    
                    <div class="glass-card rounded-[2.5rem] p-8 border-l-8 border-emerald-500 relative overflow-hidden group">
                        <div class="absolute -right-8 -bottom-8 opacity-[0.03] group-hover:scale-110 transition-transform duration-500">
                            <svg class="w-48 h-48 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                        </div>
                        <h3 class="font-bold text-slate-500 mb-4 text-[10px] uppercase tracking-widest">AI Opportunity Forecast</h3>
                        <div class="flex items-baseline gap-2">
                            <div class="text-6xl font-black text-white mb-2 stat-glow" id="stat-high-prob">0</div>
                            <span class="text-emerald-500 font-bold text-xs uppercase tracking-widest">High Probability</span>
                        </div>
                        <p class="text-xs text-slate-400 leading-relaxed max-w-[200px] mt-2">Leads with conversion probability above 75% detected across the mesh.</p>
                        <button class="w-full mt-8 py-4 bg-elite-600 hover:bg-elite-500 text-white rounded-2xl text-[10px] font-bold transition-all shadow-xl shadow-elite-500/25 uppercase tracking-[0.2em]">Deploy Auto-Engagement</button>
                    </div>
                </div>
            </div>

            <!-- Competitors -->
            <div class="glass-card rounded-[2.5rem] p-8 lg:p-10 border-b-4 border-red-500/30">
                <div class="flex items-center justify-between mb-10">
                    <div class="flex flex-col">
                        <h3 class="font-bold text-xl text-white flex items-center gap-3">
                            <svg class="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
                            Market Vulnerability Map
                        </h3>
                        <p class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-1">Competitor Weakness Analysis</p>
                    </div>
                    <button class="text-[10px] font-bold text-slate-400 hover:text-white uppercase tracking-widest border border-white/10 px-4 py-2 rounded-xl">View Details</button>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left min-w-[600px]">
                        <thead>
                            <tr class="text-[10px] font-bold text-slate-500 uppercase tracking-widest border-b border-white/5">
                                <th class="pb-6">Provider Name</th>
                                <th class="pb-6">Weakness Index</th>
                                <th class="pb-6">Signals Detected</th>
                                <th class="pb-6 text-right">Last Scan</th>
                            </tr>
                        </thead>
                        <tbody id="competitor-list" class="divide-y divide-white/5">
                            <!-- Competitor list -->
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>

    <!-- Scripts -->
    <script>
        let influenceChart, ltvChart;

        function toggleSidebar() {
            document.body.classList.toggle('sidebar-open');
            document.getElementById('sidebar').classList.toggle('-translate-x-full');
            document.getElementById('backdrop').classList.toggle('hidden');
        }

        async function updateDashboard() {
            try {
                const res = await fetch('/api/v1/stats');
                if (!res.ok) throw new Error('Network response was not ok');
                const data = await res.json();

                // Counters
                updateCount('stat-leads', data.leads_detected);
                document.getElementById('stat-conv-rate').textContent = data.conversion_rate + '%';
                updateCount('stat-messages', data.messages_analyzed);
                updateCount('stat-groups', data.total_groups_joined);
                updateCount('stat-high-prob', data.high_prob_leads);
                document.getElementById('last-updated').textContent = 'last sync: ' + new Date().toLocaleTimeString().toLowerCase();

                // Activity Log
                const logEl = document.getElementById('activity-log');
                logEl.innerHTML = data.activity_log.map(a => {
                    const urgencyColor = a.text.toLowerCase().includes('need') || a.text.toLowerCase().includes('help') ? 'text-red-500' : 'text-elite-500';
                    return `
                    <div class="p-6 hover:bg-white/[0.02] transition-colors flex items-center justify-between gap-6 group/item">
                        <div class="flex items-center gap-5">
                            <div class="w-12 h-12 rounded-2xl bg-slate-900 border border-white/5 flex items-center justify-center text-xs font-bold ${urgencyColor} uppercase shadow-inner group-hover/item:border-elite-500/30 transition-all">
                                ${a.type[0]}
                            </div>
                            <div class="flex flex-col gap-1">
                                <div class="flex items-center gap-2">
                                    <span class="text-sm font-bold text-white">@${a.user}</span>
                                    <span class="w-1 h-1 bg-slate-700 rounded-full"></span>
                                    <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">${a.type}</span>
                                </div>
                                <div class="text-[11px] text-slate-400 font-medium leading-relaxed max-w-md line-clamp-1">${a.text}</div>
                            </div>
                        </div>
                        <div class="flex flex-col items-end gap-2">
                            <span class="text-[10px] font-bold text-slate-600 tabular-nums">${a.time}</span>
                            <div class="opacity-0 group-hover/item:opacity-100 transition-opacity">
                                <button class="text-[9px] font-bold text-elite-500 uppercase tracking-widest hover:underline">Intercept</button>
                            </div>
                        </div>
                    </div>
                `}).join('') || '<div class="p-16 text-center text-slate-500 text-xs font-bold uppercase tracking-widest">Awaiting system activity...</div>';

                // Account Health
                const healthEl = document.getElementById('account-health');
                healthEl.innerHTML = data.account_health.map(a => {
                    const replyPct = (a.replies_left / 5) * 100;
                    const dmPct = (a.dms_left / 10) * 100;
                    return `
                    <div class="space-y-4">
                        <div class="flex justify-between items-center">
                            <div class="flex flex-col">
                                <span class="text-xs font-bold text-white tracking-tight">${a.phone}</span>
                                <span class="text-[9px] font-bold text-slate-500 uppercase tracking-widest mt-0.5">Session Active</span>
                            </div>
                            <span class="text-[9px] font-bold px-2.5 py-1 rounded-lg ${a.status === 'active' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'} uppercase tracking-widest">${a.status}</span>
                        </div>
                        <div class="grid grid-cols-1 gap-3">
                            <div class="space-y-1.5">
                                <div class="flex justify-between text-[8px] font-bold text-slate-500 uppercase tracking-widest">
                                    <span>Public Replies Left</span>
                                    <span>${a.replies_left}/5</span>
                                </div>
                                <div class="w-full bg-slate-900 rounded-full h-1 overflow-hidden">
                                    <div class="bg-elite-500 h-full rounded-full transition-all duration-1000" style="width: ${replyPct}%"></div>
                                </div>
                            </div>
                            <div class="space-y-1.5">
                                <div class="flex justify-between text-[8px] font-bold text-slate-500 uppercase tracking-widest">
                                    <span>Private DMs Left</span>
                                    <span>${a.dms_left}/10</span>
                                </div>
                                <div class="w-full bg-slate-900 rounded-full h-1 overflow-hidden">
                                    <div class="bg-purple-500 h-full rounded-full transition-all duration-1000" style="width: ${dmPct}%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `}).join('');

                // Competitors
                const compEl = document.getElementById('competitor-list');
                compEl.innerHTML = data.competitor_stats.map(c => `
                    <tr class="group/row hover:bg-white/[0.01] transition-colors">
                        <td class="py-6 font-bold text-white capitalize group-hover/row:text-elite-400 transition-colors">${c.name}</td>
                        <td class="py-6">
                            <div class="flex items-center gap-2">
                                <span class="px-2.5 py-1 bg-red-500/10 text-red-500 rounded-lg text-[10px] font-bold border border-red-500/20 shadow-sm">${c.score}</span>
                                <span class="text-[9px] font-bold text-slate-600 uppercase tracking-widest">High Risk</span>
                            </div>
                        </td>
                        <td class="py-6 text-sm font-medium text-slate-400 italic font-serif">"${c.complaints} specific pain points detected"</td>
                        <td class="py-6 text-right text-[10px] font-bold text-slate-600 tabular-nums uppercase">${new Date().toLocaleDateString('en-US', {month: 'short', day: 'numeric'})}</td>
                    </tr>
                `).join('') || '<tr><td colspan="4" class="py-16 text-center text-slate-500 text-xs font-bold uppercase tracking-widest">Scanning market vulnerabilities...</td></tr>';

                updateCharts(data);

            } catch (err) { console.error('SLIE Sync Error:', err); }
        }

        function updateCount(id, val) {
            const el = document.getElementById(id);
            const current = parseInt(el.textContent) || 0;
            if (current !== val) {
                el.textContent = val;
                el.classList.add('stat-glow');
                setTimeout(() => el.classList.remove('stat-glow'), 1000);
            }
        }

        function updateCharts(data) {
            const chartOptions = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#64748b',
                            usePointStyle: true,
                            padding: 20,
                            font: { size: 10, weight: '700', family: 'Plus Jakarta Sans' }
                        }
                    }
                }
            };

            const influenceCtx = document.getElementById('influenceChart').getContext('2d');
            const influenceData = [data.influence_distribution.leader, data.influence_distribution.power_user, data.influence_distribution.regular];
            
            if (influenceChart) {
                influenceChart.data.datasets[0].data = influenceData;
                influenceChart.update();
            } else {
                influenceChart = new Chart(influenceCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['COMMUNITY LEADERS', 'POWER USERS', 'REGULAR MEMBERS'],
                        datasets: [{
                            data: influenceData,
                            backgroundColor: ['#3b82f6', '#60a5fa', '#1e293b'],
                            borderWidth: 0,
                            hoverOffset: 20,
                            borderRadius: 10
                        }]
                    },
                    options: {
                        ...chartOptions,
                        cutout: '75%',
                        plugins: {
                            ...chartOptions.plugins,
                            legend: { ...chartOptions.plugins.legend, position: 'right' }
                        }
                    }
                });
            }

            const ltvCtx = document.getElementById('ltvChart').getContext('2d');
            const ltvLabels = Object.keys(data.ltv_distribution).map(k => k.replace(/_/g, ' ').toUpperCase());
            const ltvValues = Object.values(data.ltv_distribution);
            
            if (ltvChart) {
                ltvChart.data.labels = ltvLabels;
                ltvChart.data.datasets[0].data = ltvValues;
                ltvChart.update();
            } else {
                const gradient = ltvCtx.createLinearGradient(0, 0, 0, 400);
                gradient.addColorStop(0, '#60a5fa');
                gradient.addColorStop(1, '#3b82f6');

                ltvChart = new Chart(ltvCtx, {
                    type: 'bar',
                    data: {
                        labels: ltvLabels,
                        datasets: [{
                            data: ltvValues,
                            backgroundColor: gradient,
                            borderRadius: 12,
                            barThickness: 25,
                            hoverBackgroundColor: '#fff'
                        }]
                    },
                    options: {
                        ...chartOptions,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { 
                                grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false }, 
                                ticks: { color: '#475569', font: { size: 9, weight: '700' } } 
                            },
                            x: { 
                                grid: { display: false }, 
                                ticks: { color: '#475569', font: { size: 8, weight: '700' } } 
                            }
                        }
                    }
                });
            }
        }

        updateDashboard();
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"""
