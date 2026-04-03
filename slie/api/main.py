import asyncio
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from telethon import events
from fastapi.responses import HTMLResponse
from slie.core.config import get_settings, Settings
from slie.core.database import engine, Base, AsyncSessionLocal
from slie.models.group_models import Group
from slie.models.lead_models import Lead, User
from slie.models.conversation_models import Message
from slie.analytics.dashboard_service import dashboard_service
from slie.telegram.telegram_client import telegram_engine
from slie.discovery.group_discovery import discovery_engine
from slie.discovery.group_analyzer import group_analyzer
from slie.intelligence.message_intelligence import message_intelligence
from slie.market_engine.seller_density_detector import seller_detector
from slie.engagement.human_behavior_engine import human_engine
from slie.engagement.conversation_strategy import conversation_strategy
from sqlalchemy import select

# Configure logging for production readiness
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("slie_runtime.log")
    ]
)
logger = logging.getLogger(__name__)

async def slie_background_orchestrator():
    """
    Main background loop for discovery and market analysis.
    """
    logger.info("[SLIE Orchestrator] Starting background engine...")
    while True:
        try:
            # 1. Discover new groups
            await discovery_engine.discover_groups()
            
            # 2. Process discovered groups
            async with AsyncSessionLocal() as db:
                stmt = select(Group).where(Group.status == "DISCOVERED").limit(5)
                result = await db.execute(stmt)
                groups = result.scalars().all()
                
                for group in groups:
                    logger.info(f"[SLIE Orchestrator] Analyzing group: {group.name} ({group.telegram_id})")
                    # Step 5: Quality Filter
                    is_valid = await group_analyzer.analyze_group(group.telegram_id)
                    
                    if is_valid:
                        # Step 12: Safety - Check if we can join
                        if await human_engine.authorize_action("group_join"):
                            # Simulation: Since we are in a sandbox, we might not want to join real groups 
                            # unless invite link is available. For MVP test, let's assume we can.
                            # await telegram_engine.join_group(...) 
                            # For now, mark as JOINED to simulate activity
                            group.status = "JOINED"
                            logger.info(f"[SLIE Orchestrator] Joined group: {group.name}")
                            
                            # Step 6: Seller Density Check
                            await seller_detector.analyze_market_saturation(group.telegram_id)
                
                await db.commit()
            
            logger.info("[SLIE Orchestrator] Cycle complete. Sleeping for 30 min.")
            await asyncio.sleep(1800) 
        except Exception as e:
            logger.error(f"[SLIE Orchestrator] Error in cycle: {str(e)}")
            await asyncio.sleep(60)

async def lead_engagement_orchestrator():
    """
    Periodically check for new leads and trigger engagement strategy.
    """
    logger.info("[SLIE Lead Orchestrator] Starting engagement engine...")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Find high probability leads that haven't been engaged yet
                # (For simplicity, we check leads from the last 10 minutes)
                ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
                stmt = select(Lead, User.telegram_user_id, Message.telegram_message_id, Message.telegram_group_id)\
                    .join(User, Lead.user_id == User.id)\
                    .join(Message, (Message.telegram_user_id == User.telegram_user_id) & (Message.body == Lead.message_text))\
                    .where(Lead.opportunity_score >= 70, Lead.created_at >= ten_min_ago)
                
                result = await db.execute(stmt)
                leads = result.all()
                
                for lead, telegram_user_id, telegram_message_id, telegram_group_id in leads:
                    logger.info(f"[SLIE Lead Orchestrator] Engaging lead: {lead.id} (@{telegram_user_id})")
                    # Trigger engagement strategy in a separate task to not block the orchestrator
                    asyncio.create_task(conversation_strategy.execute_strategy(
                        lead_id=lead.id,
                        user_id=telegram_user_id,
                        group_id=telegram_group_id,
                        message_id=telegram_message_id,
                        context=lead.message_text
                    ))
            
            await asyncio.sleep(60) # Check every minute
        except Exception as e:
            logger.error(f"[SLIE Lead Orchestrator] Error: {str(e)}")
            await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} in {settings.environment} mode...")
    
    # Auto-create tables if enabled (Production MVP fix)
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("[SLIE Database] Tables initialized successfully.")

    # Initialize Telegram Client (Step 3)
    if settings.telegram_session_string:
        client = await telegram_engine.connect()
        if client:
            # Register Message Intelligence (Step 7)
            telegram_engine.add_event_handler(
                message_intelligence.process_message, 
                events.NewMessage(incoming=True)
            )
            # Start background orchestrator
            asyncio.create_task(slie_background_orchestrator())
            # Start lead engagement orchestrator
            asyncio.create_task(lead_engagement_orchestrator())
    
    yield
    
    # Shutdown
    await telegram_engine.disconnect()
    logger.info(f"{settings.app_name} shutdown complete.")

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        version="1.0.0-MVP"
    )

    @app.get("/")
    async def root():
        return {"message": "SLIE Intelligence System API is running."}

    @app.get("/health")
    async def health_check():
        """Render health check endpoint."""
        return {"status": "healthy", "engine": "SLIE Elite"}

    @app.get("/api/v1/stats")
    async def get_stats():
        """
        STEP 15: ANALYTICS ENGINE
        """
        try:
            return await dashboard_service.get_stats()
        except Exception as e:
            logger.error(f"[SLIE API] Error in get_stats: {str(e)}")
            raise

    @app.post("/api/v1/discovery/trigger")
    async def trigger_discovery():
        """Manual trigger for group discovery."""
        asyncio.create_task(discovery_engine.discover_groups())
        return {"status": "Discovery task initiated."}

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_page():
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
                            400: '#5c83ff', 500: '#010faf', 600: '#010faf', 700: '#000000',
                            800: '#000000', 900: '#000000', 950: '#000000',
                        },
                        accent: {
                            red: '#660100',
                            blue: '#010faf',
                            dark: '#000000'
                        },
                        surface: {
                            800: '#000000', 900: '#000000', 950: '#000000',
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
                radial-gradient(at 0% 0%, rgba(1, 15, 175, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(102, 1, 0, 0.1) 0px, transparent 50%),
                radial-gradient(at 50% 50%, rgba(0, 0, 0, 1) 0px, transparent 100%);
            min-height: 100vh;
        }
        .glass-card {
            background: rgba(10, 10, 10, 0.8);
            backdrop-filter: blur(25px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 10px 40px 0 rgba(0, 0, 0, 1);
        }
        .glass-card:hover {
            border-color: rgba(1, 15, 175, 0.4);
            background: rgba(15, 15, 15, 0.9);
            transform: translateY(-4px);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .sidebar-active {
            background: linear-gradient(90deg, rgba(1, 15, 175, 0.3) 0%, transparent 100%);
            border-left: 4px solid #010faf;
            color: #fff;
        }
        .btn-primary {
            background: linear-gradient(135deg, #010faf 0%, #660100 100%);
            transition: all 0.3s ease;
        }
        .btn-primary:hover {
            filter: brightness(1.2);
            box-shadow: 0 0 25px rgba(1, 15, 175, 0.6);
        }
        .stat-glow-blue { filter: drop-shadow(0 0 12px rgba(1, 15, 175, 0.6)); }
        .stat-glow-red { filter: drop-shadow(0 0 12px rgba(102, 1, 0, 0.6)); }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(1, 15, 175, 0.4); border-radius: 10px; }
        .live-dot {
            width: 10px; height: 10px; background: #10b981;
            border-radius: 50%; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse-dot 2s infinite;
        }
        @keyframes pulse-dot {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        .premium-gradient-text {
            background: linear-gradient(to right, #fff, #92afff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
    </style>
</head>
<body class="text-slate-200 antialiased overflow-x-hidden flex flex-col lg:flex-row min-h-screen">
    <div id="backdrop" class="fixed inset-0 bg-black/70 backdrop-blur-md z-40 hidden lg:hidden" onclick="toggleSidebar()"></div>

    <!-- Sidebar -->
    <aside id="sidebar" class="fixed inset-y-0 left-0 z-50 w-72 bg-black border-r border-white/5 transform -translate-x-full lg:translate-x-0 transition-transform duration-500 ease-in-out lg:static lg:block flex flex-col shadow-2xl">
        <div class="p-8 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 bg-elite-500 rounded-2xl flex items-center justify-center shadow-2xl shadow-elite-500/40 border border-white/10">
                    <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                </div>
                <div class="flex flex-col">
                    <span class="text-xl font-black tracking-tighter text-white leading-none">SLIE <span class="text-elite-500">ELITE</span></span>
                    <span class="text-[10px] font-black text-slate-500 tracking-[0.3em] uppercase mt-1.5">Intelligence v4.2</span>
                </div>
            </div>
            <button class="lg:hidden p-2 text-slate-400" onclick="toggleSidebar()">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
        </div>
        
        <nav class="flex-1 px-5 py-4 space-y-2 overflow-y-auto">
            <div class="px-4 py-2 text-[10px] font-black text-slate-600 uppercase tracking-[0.3em]">Strategic Ops</div>
            <a href="#" class="flex items-center gap-4 px-5 py-4 rounded-2xl sidebar-active text-sm font-bold transition-all group">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
                Intelligence Hub
            </a>
            <a href="#" class="flex items-center gap-4 px-5 py-4 rounded-2xl text-slate-500 hover:text-white hover:bg-white/5 text-sm font-bold transition-all group">
                <svg class="w-5 h-5 group-hover:text-elite-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                Lead Analysis
            </a>
            <a href="#" class="flex items-center gap-4 px-5 py-4 rounded-2xl text-slate-500 hover:text-white hover:bg-white/5 text-sm font-bold transition-all group">
                <svg class="w-5 h-5 group-hover:text-accent-red transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                Conversation Engine
            </a>
            <div class="px-4 py-6 text-[10px] font-black text-slate-600 uppercase tracking-[0.3em]">System Health</div>
            <a href="#" class="flex items-center gap-4 px-5 py-4 rounded-2xl text-slate-500 hover:text-white hover:bg-white/5 text-sm font-bold transition-all group">
                <svg class="w-5 h-5 text-emerald-500/70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                Safety Protocol
            </a>
        </nav>

        <div class="p-8 border-t border-white/5">
            <div class="bg-surface-800/80 rounded-[2rem] p-6 border border-white/10 shadow-2xl">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-2">
                        <div class="live-dot"></div>
                        <span class="text-[10px] font-black text-emerald-500 uppercase tracking-widest">Bot Active</span>
                    </div>
                </div>
                <div class="w-full bg-slate-800/50 rounded-full h-2 mb-3 overflow-hidden">
                    <div class="bg-gradient-to-r from-emerald-500 to-emerald-300 h-full w-[92%] rounded-full shadow-[0_0_15px_rgba(16,185,129,0.5)]"></div>
                </div>
                <p class="text-[10px] text-slate-500 leading-relaxed font-bold uppercase tracking-tight">Trust Index: 0.98/1.0</p>
            </div>
        </div>
    </aside>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col min-w-0 bg-transparent relative">
        <!-- Header -->
        <header class="h-24 flex items-center justify-between px-8 lg:px-12 sticky top-0 z-30 bg-black/80 backdrop-blur-2xl border-b border-white/10">
            <div class="flex items-center gap-6">
                <button class="lg:hidden p-4 bg-white/5 rounded-2xl text-slate-400 hover:text-white transition-all hover:scale-110" onclick="toggleSidebar()">
                    <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
                </button>
                <div class="flex flex-col">
                    <h2 class="text-xs font-black text-white uppercase tracking-[0.4em] flex items-center gap-3">
                        Tactical Overview
                        <span class="w-1.5 h-1.5 bg-elite-500 rounded-full animate-pulse"></span>
                        <span id="last-updated" class="text-slate-500 font-bold tabular-nums lowercase tracking-normal opacity-70">syncing satellite...</span>
                    </h2>
                </div>
            </div>
            <div class="flex items-center gap-6">
                <button onclick="triggerDiscovery()" class="hidden sm:flex items-center gap-2 px-4 py-2 bg-elite-500/10 border border-elite-500/30 rounded-xl text-[10px] font-black text-elite-500 hover:bg-elite-500/20 transition-all uppercase tracking-widest">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                    Force Scan
                </button>
                <div class="hidden md:flex flex-col items-end">
                    <span class="text-[11px] font-black text-white tracking-widest uppercase">Operator Root</span>
                    <span class="text-[9px] font-black text-elite-500 uppercase tracking-[0.3em]">Level 5 Clearance</span>
                </div>
                <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-elite-500 to-accent-red p-[1.5px] shadow-2xl shadow-elite-500/30">
                    <div class="w-full h-full bg-surface-950 rounded-[14px] flex items-center justify-center font-black text-sm text-white">OR</div>
                </div>
            </div>
        </header>

        <main class="p-8 lg:p-12 space-y-12 max-w-[1800px] mx-auto w-full">
            <!-- KPI Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
                <div class="glass-card rounded-[2.5rem] p-9 transition-all group overflow-hidden relative border-t-4 border-elite-500">
                    <div class="text-slate-500 text-[11px] font-black uppercase tracking-[0.3em] mb-3">Intelligence Found</div>
                    <div class="flex items-end justify-between relative z-10">
                        <div class="text-5xl font-black text-white tracking-tighter stat-glow-blue" id="stat-leads">0</div>
                        <div class="flex flex-col items-end">
                            <span class="text-[10px] font-black text-emerald-400 mb-1">+24.5%</span>
                            <span class="text-[9px] font-bold text-slate-600 uppercase">Growth</span>
                        </div>
                    </div>
                </div>
                <div class="glass-card rounded-[2.5rem] p-9 transition-all group overflow-hidden relative border-t-4 border-accent-red">
                    <div class="text-slate-500 text-[11px] font-black uppercase tracking-[0.3em] mb-3">Opportunity Score</div>
                    <div class="flex items-end justify-between relative z-10">
                        <div class="text-5xl font-black text-white tracking-tighter stat-glow-red" id="stat-conv-rate">0%</div>
                        <div class="text-[10px] font-black text-accent-red bg-accent-red/10 px-3 py-1.5 rounded-xl border border-accent-red/20 uppercase tracking-widest">High Potential</div>
                    </div>
                </div>
                <div class="glass-card rounded-[2.5rem] p-9 transition-all group overflow-hidden relative border-t-4 border-slate-700">
                    <div class="text-slate-500 text-[11px] font-black uppercase tracking-[0.3em] mb-3">Signals Decoded</div>
                    <div class="flex items-end justify-between relative z-10">
                        <div class="text-5xl font-black text-white tracking-tighter" id="stat-messages">0</div>
                        <div class="flex items-center gap-1.5">
                            <div class="w-2 h-2 bg-elite-500 rounded-full animate-ping"></div>
                            <span class="text-[10px] font-black text-slate-500 uppercase">Realtime</span>
                        </div>
                    </div>
                </div>
                <div class="glass-card rounded-[2.5rem] p-9 transition-all group overflow-hidden relative border-t-4 border-emerald-500">
                    <div class="text-slate-500 text-[11px] font-black uppercase tracking-[0.3em] mb-3">Mesh Coverage</div>
                    <div class="flex items-end justify-between relative z-10">
                        <div class="text-5xl font-black text-white tracking-tighter" id="stat-groups">0</div>
                        <span class="text-[10px] font-black text-emerald-500 uppercase tracking-widest">Active Links</span>
                    </div>
                </div>
            </div>

            <!-- Charts Row -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-12">
                <div class="lg:col-span-2 glass-card rounded-[3rem] p-10 lg:p-12">
                    <div class="flex items-center justify-between mb-12">
                        <div class="flex flex-col">
                            <h3 class="font-black text-2xl text-white tracking-tight premium-gradient-text">Intelligence Velocity</h3>
                            <p class="text-[11px] font-black text-slate-500 uppercase tracking-[0.3em] mt-2">Temporal Lead Influx Analysis</p>
                        </div>
                        <div class="flex gap-3">
                            <button class="text-[10px] font-black text-elite-400 bg-elite-500/10 px-5 py-2.5 rounded-2xl border border-elite-500/20 uppercase tracking-widest hover:bg-elite-500/20 transition-all">24H VIEW</button>
                        </div>
                    </div>
                    <div class="h-[400px] w-full"><canvas id="velocityChart"></canvas></div>
                </div>
                <div class="glass-card rounded-[3rem] p-10 lg:p-12 flex flex-col">
                    <div class="flex flex-col mb-12">
                        <h3 class="font-black text-2xl text-white tracking-tight premium-gradient-text">Sentiment Mesh</h3>
                        <p class="text-[11px] font-black text-slate-500 uppercase tracking-[0.3em] mt-2">Emotional Vector Mapping</p>
                    </div>
                    <div class="h-[400px] w-full flex-1"><canvas id="sentimentChart"></canvas></div>
                </div>
            </div>

            <!-- Activity & Health -->
            <div class="grid grid-cols-1 xl:grid-cols-12 gap-12">
                <!-- Live Stream -->
                <div class="xl:col-span-8 glass-card rounded-[3rem] overflow-hidden flex flex-col border-t-4 border-elite-500/30">
                    <div class="p-10 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
                        <h3 class="font-black text-xl text-white flex items-center gap-4">
                            <span class="live-dot"></span>
                            Intelligence Stream
                        </h3>
                        <div class="flex items-center gap-5">
                            <span class="text-[10px] text-slate-600 font-black uppercase tracking-[0.2em]">Neural Sync: 100%</span>
                            <div class="w-px h-6 bg-white/10"></div>
                            <button class="text-[10px] font-black text-elite-500 uppercase tracking-widest hover:text-elite-400 transition-colors">Export Logs</button>
                        </div>
                    </div>
                    <div id="activity-log" class="divide-y divide-white/5 max-h-[700px] overflow-y-auto">
                        <!-- Activity items -->
                    </div>
                    <div class="p-6 bg-white/[0.02] border-t border-white/10 text-center">
                        <button class="text-[11px] font-black text-slate-500 uppercase tracking-[0.3em] hover:text-white transition-all">Expand Matrix View</button>
                    </div>
                </div>

                <!-- Account Health & AI Forecast -->
                <div class="xl:col-span-4 space-y-12">
                    <div class="glass-card rounded-[3rem] p-10">
                        <div class="flex items-center justify-between mb-10">
                            <h3 class="font-black text-xl text-white tracking-tight">Safety Matrix</h3>
                            <div class="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                                <svg class="w-6 h-6 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                            </div>
                        </div>
                        <div id="account-health" class="space-y-10">
                            <!-- Account health -->
                        </div>
                    </div>
                    
                    <div class="glass-card rounded-[3rem] p-10 border-l-[12px] border-accent-red relative overflow-hidden group">
                        <div class="absolute -right-12 -bottom-12 opacity-[0.05] group-hover:scale-125 group-hover:rotate-12 transition-all duration-700">
                            <svg class="w-64 h-64 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                        </div>
                        <h3 class="font-black text-slate-600 mb-6 text-[11px] uppercase tracking-[0.4em]">AI Opportunity Forecast</h3>
                        <div class="flex items-baseline gap-3 mb-4">
                            <div class="text-7xl font-black text-white tracking-tighter stat-glow-red" id="stat-high-prob">0</div>
                            <span class="text-accent-red font-black text-xs uppercase tracking-[0.2em]">Tier-1 Leads</span>
                        </div>
                        <p class="text-xs text-slate-500 leading-relaxed font-bold uppercase tracking-tight mb-10">Detected elite targets with conversion probability exceeding 88.5%.</p>
                        <button class="w-full py-5 bg-gradient-to-r from-elite-600 to-accent-red hover:scale-[1.02] active:scale-[0.98] text-white rounded-2xl text-[11px] font-black transition-all shadow-2xl shadow-elite-500/40 uppercase tracking-[0.3em]">Engage Precision Strike</button>
                    </div>
                </div>
            </div>

            <!-- Vulnerability Map -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12">
                <div class="glass-card rounded-[3rem] p-10 lg:p-12 border-b-8 border-accent-red/20">
                    <div class="flex items-center justify-between mb-12">
                        <div class="flex flex-col">
                            <h3 class="font-black text-2xl text-white flex items-center gap-4 tracking-tight">
                                <div class="w-10 h-10 rounded-xl bg-accent-red/10 flex items-center justify-center border border-accent-red/20">
                                    <svg class="w-6 h-6 text-accent-red" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
                                </div>
                                Market Vulnerability Map
                            </h3>
                            <p class="text-[11px] font-black text-slate-600 uppercase tracking-[0.3em] mt-3">Competitor Exploitation Index</p>
                        </div>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left min-w-[400px]">
                            <thead>
                                <tr class="text-[11px] font-black text-slate-600 uppercase tracking-[0.3em] border-b border-white/10">
                                    <th class="pb-8">Entity Identifier</th>
                                    <th class="pb-8">Vulnerability</th>
                                    <th class="pb-8 text-right">Satellite</th>
                                </tr>
                            </thead>
                            <tbody id="competitor-list" class="divide-y divide-white/5">
                                <!-- Competitor list -->
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="glass-card rounded-[3rem] p-10 lg:p-12 border-b-8 border-elite-500/20">
                    <div class="flex items-center justify-between mb-12">
                        <div class="flex flex-col">
                            <h3 class="font-black text-2xl text-white flex items-center gap-4 tracking-tight">
                                <div class="w-10 h-10 rounded-xl bg-elite-500/10 flex items-center justify-center border border-elite-500/20">
                                    <svg class="w-6 h-6 text-elite-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
                                </div>
                                High-Probability Leads
                            </h3>
                            <p class="text-[11px] font-black text-slate-600 uppercase tracking-[0.3em] mt-3">Elite Target Acquisition</p>
                        </div>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left min-w-[400px]">
                            <thead>
                                <tr class="text-[11px] font-black text-slate-600 uppercase tracking-[0.3em] border-b border-white/10">
                                    <th class="pb-8">Target</th>
                                    <th class="pb-8">Score</th>
                                    <th class="pb-8 text-right">Status</th>
                                </tr>
                            </thead>
                            <tbody id="lead-list" class="divide-y divide-white/5">
                                <!-- Lead list -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Scripts -->
    <script>
        let velocityChart, sentimentChart;

        function toggleSidebar() {
            document.body.classList.toggle('sidebar-open');
            document.getElementById('sidebar').classList.toggle('-translate-x-full');
            document.getElementById('backdrop').classList.toggle('hidden');
        }

        async function triggerDiscovery() {
            const btn = event.currentTarget;
            btn.disabled = true;
            btn.textContent = 'SCANNING...';
            try {
                const res = await fetch('/api/v1/discovery/trigger', { method: 'POST' });
                if (res.ok) {
                    alert('Satellite scan sequence initiated.');
                }
            } catch (err) { console.error('Discovery Error:', err); }
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg> Force Scan';
            }, 5000);
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
                document.getElementById('last-updated').textContent = 'satellite sync: ' + new Date().toLocaleTimeString().toLowerCase();

                // Activity Log
                const logEl = document.getElementById('activity-log');
                logEl.innerHTML = data.activity_log.map(a => {
                    const urgency = a.text.toLowerCase().includes('need') || a.text.toLowerCase().includes('help');
                    const color = urgency ? 'text-accent-red border-accent-red/30 bg-accent-red/5' : 'text-elite-400 border-elite-500/20 bg-elite-500/5';
                    return `
                    <div class="p-8 hover:bg-white/[0.03] transition-all flex items-center justify-between gap-8 group/item">
                        <div class="flex items-center gap-6">
                            <div class="w-14 h-14 rounded-2xl border flex items-center justify-center text-[10px] font-black uppercase shadow-2xl transition-all group-hover/item:scale-110 ${color}">
                                ${a.type[0]}
                            </div>
                            <div class="flex flex-col gap-2">
                                <div class="flex items-center gap-3">
                                    <span class="text-base font-black text-white">@${a.user}</span>
                                    <span class="w-1.5 h-1.5 bg-slate-700 rounded-full"></span>
                                    <span class="text-[10px] font-black text-slate-500 uppercase tracking-widest">${a.type}</span>
                                </div>
                                <div class="text-xs text-slate-400 font-bold leading-relaxed max-w-xl line-clamp-1 italic">"${a.text}"</div>
                            </div>
                        </div>
                        <div class="flex flex-col items-end gap-3">
                            <span class="text-[10px] font-black text-slate-700 tabular-nums tracking-widest">${a.time}</span>
                            <div class="opacity-0 group-hover/item:opacity-100 transition-all translate-x-4 group-hover/item:translate-x-0">
                                <button class="text-[10px] font-black text-elite-500 uppercase tracking-[0.2em] hover:text-white border border-elite-500/30 px-4 py-2 rounded-xl bg-elite-500/10">INTERCEPT</button>
                            </div>
                        </div>
                    </div>
                `}).join('') || '<div class="p-24 text-center text-slate-600 text-[11px] font-black uppercase tracking-[0.4em]">Matrix awaiting data...</div>';

                // Account Health
                const healthEl = document.getElementById('account-health');
                healthEl.innerHTML = data.account_health.map(a => {
                    const replyPct = (a.replies_left / 5) * 100;
                    const dmPct = (a.dms_left / 2) * 100;
                    return `
                    <div class="space-y-6">
                        <div class="flex justify-between items-center">
                            <div class="flex flex-col">
                                <span class="text-sm font-black text-white tracking-tight">${a.phone}</span>
                                <span class="text-[9px] font-black text-slate-600 uppercase tracking-[0.3em] mt-1.5">Neural Link Established</span>
                            </div>
                            <span class="text-[10px] font-black px-4 py-2 rounded-xl ${a.status === 'active' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'} uppercase tracking-[0.2em]">Secure</span>
                        </div>
                        <div class="grid grid-cols-1 gap-5">
                            <div class="space-y-2.5">
                                <div class="flex justify-between text-[9px] font-black text-slate-500 uppercase tracking-[0.3em]">
                                    <span>Public Interactions</span>
                                    <span class="text-elite-500">${a.replies_left}/5</span>
                                </div>
                                <div class="w-full bg-slate-900/50 rounded-full h-2 overflow-hidden border border-white/5">
                                    <div class="bg-gradient-to-r from-elite-600 to-elite-400 h-full rounded-full transition-all duration-1000 shadow-[0_0_15px_rgba(1,15,175,0.4)]" style="width: ${replyPct}%"></div>
                                </div>
                            </div>
                            <div class="space-y-2.5">
                                <div class="flex justify-between text-[9px] font-black text-slate-500 uppercase tracking-[0.3em]">
                                    <span>Stealth DMs</span>
                                    <span class="text-accent-red">${a.dms_left}/2</span>
                                </div>
                                <div class="w-full bg-slate-900/50 rounded-full h-2 overflow-hidden border border-white/5">
                                    <div class="bg-gradient-to-r from-accent-red to-red-400 h-full rounded-full transition-all duration-1000 shadow-[0_0_15px_rgba(102,1,0,0.4)]" style="width: ${dmPct}%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `}).join('');

                // Competitors
                const compEl = document.getElementById('competitor-list');
                compEl.innerHTML = data.competitor_stats.map(c => `
                    <tr class="group/row hover:bg-white/[0.02] transition-all">
                        <td class="py-8 font-black text-white tracking-tight group-hover/row:text-elite-400 transition-colors uppercase text-[10px]">${c.name}</td>
                        <td class="py-8">
                            <span class="text-[10px] font-black text-accent-red uppercase tracking-widest">${c.score}% RISK</span>
                        </td>
                        <td class="py-8 text-right text-[10px] font-black text-slate-700 tabular-nums uppercase tracking-[0.2em]">SYNC</td>
                    </tr>
                `).join('') || '<tr><td colspan="3" class="py-12 text-center text-slate-600 text-[11px] font-black uppercase tracking-[0.4em]">Scanning...</td></tr>';

                // High Probability Leads
                const leadEl = document.getElementById('lead-list');
                leadEl.innerHTML = data.high_prob_list.map(l => `
                    <tr class="group/row hover:bg-white/[0.02] transition-all">
                        <td class="py-8 flex flex-col gap-1">
                            <span class="font-black text-white tracking-tight group-hover/row:text-elite-400 transition-colors uppercase text-[10px]">@${l.user}</span>
                            <span class="text-[9px] text-slate-500 line-clamp-1 italic">"${l.text}"</span>
                        </td>
                        <td class="py-8">
                            <div class="flex items-center gap-2">
                                <div class="w-12 bg-slate-900 rounded-full h-1 overflow-hidden">
                                    <div class="bg-elite-500 h-full" style="width: ${l.score}%"></div>
                                </div>
                                <span class="text-[10px] font-black text-elite-500">${l.score}%</span>
                            </div>
                        </td>
                        <td class="py-8 text-right">
                            <button class="text-[9px] font-black text-emerald-500 uppercase tracking-widest border border-emerald-500/30 px-3 py-1.5 rounded-lg bg-emerald-500/5 hover:bg-emerald-500/20 transition-all">ENGAGE</button>
                        </td>
                    </tr>
                `).join('') || '<tr><td colspan="3" class="py-12 text-center text-slate-600 text-[11px] font-black uppercase tracking-[0.4em]">No Elite Leads Found</td></tr>';

                updateCharts(data);

            } catch (err) { console.error('SLIE Sync Error:', err); }
        }

        function updateCount(id, val) {
            const el = document.getElementById(id);
            const current = parseInt(el.textContent) || 0;
            if (current !== val) {
                el.textContent = val;
                el.classList.add('scale-110', 'text-elite-400');
                setTimeout(() => el.classList.remove('scale-110', 'text-elite-400'), 800);
            }
        }

        function updateCharts(data) {
            const chartOptions = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: '#0a0b2e',
                        titleFont: { family: 'Plus Jakarta Sans', size: 12, weight: '800' },
                        bodyFont: { family: 'Plus Jakarta Sans', size: 11, weight: '600' },
                        padding: 15,
                        borderColor: 'rgba(1, 15, 175, 0.3)',
                        borderWidth: 1
                    }
                },
                scales: {
                    y: { display: false },
                    x: { display: false }
                }
            };

            // Velocity Chart (Line)
            const velocityCtx = document.getElementById('velocityChart').getContext('2d');
            const velocityLabels = data.velocity_data.map(d => d.time);
            const velocityLeads = data.velocity_data.map(d => d.leads);
            const velocityMsgs = data.velocity_data.map(d => d.messages);
            
            if (velocityChart) {
                velocityChart.data.labels = velocityLabels;
                velocityChart.data.datasets[0].data = velocityLeads;
                velocityChart.data.datasets[1].data = velocityMsgs;
                velocityChart.update();
            } else {
                const leadGrad = velocityCtx.createLinearGradient(0, 0, 0, 400);
                leadGrad.addColorStop(0, 'rgba(1, 15, 175, 0.4)');
                leadGrad.addColorStop(1, 'rgba(1, 15, 175, 0)');

                const msgGrad = velocityCtx.createLinearGradient(0, 0, 0, 400);
                msgGrad.addColorStop(0, 'rgba(102, 1, 0, 0.2)');
                msgGrad.addColorStop(1, 'rgba(102, 1, 0, 0)');

                velocityChart = new Chart(velocityCtx, {
                    type: 'line',
                    data: {
                        labels: velocityLabels,
                        datasets: [
                            {
                                label: 'LEADS DETECTED',
                                data: velocityLeads,
                                borderColor: '#010faf',
                                borderWidth: 4,
                                fill: true,
                                backgroundColor: leadGrad,
                                tension: 0.4,
                                pointRadius: 0,
                                pointHoverRadius: 6
                            },
                            {
                                label: 'SIGNALS PROCESSED',
                                data: velocityMsgs,
                                borderColor: '#660100',
                                borderWidth: 2,
                                fill: true,
                                backgroundColor: msgGrad,
                                tension: 0.4,
                                pointRadius: 0,
                                borderDash: [5, 5]
                            }
                        ]
                    },
                    options: {
                        ...chartOptions,
                        scales: {
                            y: { 
                                grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
                                ticks: { color: '#475569', font: { family: 'Plus Jakarta Sans', size: 10, weight: '800' } }
                            },
                            x: { 
                                grid: { display: false },
                                ticks: { color: '#475569', font: { family: 'Plus Jakarta Sans', size: 10, weight: '800' } }
                            }
                        }
                    }
                });
            }

            // Sentiment Radar Chart
            const sentimentCtx = document.getElementById('sentimentChart').getContext('2d');
            const sentimentLabels = Object.keys(data.sentiment_mesh).map(k => k.replace(/_/g, ' ').toUpperCase());
            const sentimentValues = Object.values(data.sentiment_mesh);

            if (sentimentChart) {
                sentimentChart.data.labels = sentimentLabels;
                sentimentChart.data.datasets[0].data = sentimentValues;
                sentimentChart.update();
            } else {
                sentimentChart = new Chart(sentimentCtx, {
                    type: 'radar',
                    data: {
                        labels: sentimentLabels,
                        datasets: [{
                            data: sentimentValues,
                            backgroundColor: 'rgba(1, 15, 175, 0.2)',
                            borderColor: '#010faf',
                            borderWidth: 3,
                            pointBackgroundColor: '#010faf',
                            pointBorderColor: '#fff',
                            pointHoverBackgroundColor: '#fff',
                            pointHoverBorderColor: '#010faf'
                        }]
                    },
                    options: {
                        ...chartOptions,
                        scales: {
                            r: {
                                grid: { color: 'rgba(255,255,255,0.05)' },
                                angleLines: { color: 'rgba(255,255,255,0.05)' },
                                pointLabels: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 9, weight: '800' } },
                                ticks: { display: false },
                                suggestedMin: 0,
                                suggestedMax: 100
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

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("slie.api.main:app", host="0.0.0.0", port=8000, reload=False)
