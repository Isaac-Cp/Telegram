import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, desc
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.group import Group
from app.models.opportunity_cluster import OpportunityCluster
from app.models.enums import ConversionStage
from app.services.ai_service import ai_service
from app.services.telegram_client import telegram_client_manager

from app.models.persona import Persona

from app.models.problem_trend import ProblemTrend

logger = logging.getLogger(__name__)

PERSONAS = {
    "Aiden": {
        "name": "Aiden",
        "role": "Senior IPTV Architect",
        "expertise": "IPTV Systems & Scaling",
        "tone": "Technical, professional, authoritative"
    },
    "Luca": {
        "name": "Luca",
        "role": "Streaming Network Engineer",
        "expertise": "Network Latency & Buffering",
        "tone": "Direct, engineering-focused, detailed"
    },
    "Maya": {
        "name": "Maya",
        "role": "Infrastructure Specialist",
        "expertise": "Server Architecture & Uptime",
        "tone": "Strategic, helpful, insightful"
    }
}

class PowerUpgradesService:
    def __init__(self):
        self._personas_initialized = False

    def _initialize_personas(self):
        """Initialize personas in the database if they don't exist."""
        if self._personas_initialized:
            return

        with SessionLocal() as db:
            count = db.query(func.count(Persona.id)).scalar()
            if count == 0:
                for name, data in PERSONAS.items():
                    persona = Persona(
                        name=data["name"],
                        role=data["role"],
                        expertise=data["expertise"],
                        tone=data["tone"]
                    )
                    db.add(persona)
                db.commit()
                logger.info("Initialized default expert personas.")
            self._personas_initialized = True

    async def detect_lead_temperature(self, lead_id: str, message_text: str):
        """
        Elite Module 2: Lead Temperature Detection Engine.
        Classify leads based on purchase intent.
        
        AI PROMPT:
        Classify the following IPTV message intent. 
        Return one of the following: 
        COLD – general complaint 
        WARM – asking questions 
        HOT – actively looking for provider 
        """
        prompt = f"""
        Classify the following IPTV message intent. 
 
        Return one of the following: 
 
        COLD – general complaint 
        WARM – asking questions 
        HOT – actively looking for provider 
 
        Examples of HOT leads:
        - Any IPTV provider recommendations? 
        - Looking for reliable IPTV 
        - Need a new IPTV service
        
        INPUT:
        {message_text}
        """
        
        try:
            content = await ai_service.chat_completion(prompt=prompt)
            if not content:
                return
                
            raw_temp = content.strip().upper()
            temperature = "COLD" # Default
            
            # Elite Module 2 Mapping
            if "HOT" in raw_temp:
                temperature = "HOT"
            elif "WARM" in raw_temp:
                temperature = "WARM"
            
            with SessionLocal() as db:
                lead = db.get(Lead, lead_id)
                if lead:
                    lead.lead_temperature = temperature
                    db.commit()
                    logger.info(f"SLIE Temperature Engine: Lead {lead_id} classified as {temperature}")
        except Exception as e:
            logger.error(f"Temperature detection failed: {e}")

    def select_persona(self, lead: Lead) -> dict:
        """
        Elite Module 5: Persona Rotation Engine.
        Rotate expert personas for conversations to make responses more natural.
        Assign persona when lead conversation begins.
        Maintain same persona throughout conversation.
        """
        self._initialize_personas()
        with SessionLocal() as db:
            # Check if lead already has an assigned persona
            if lead.persona_id:
                persona = db.query(Persona).filter(Persona.name == lead.persona_id).first()
                if persona:
                    return {
                        "name": persona.name,
                        "role": persona.role,
                        "expertise": persona.expertise,
                        "tone": persona.tone
                    }

            # Rotate: Select a random persona from the database
            import random
            all_personas = db.query(Persona).all()
            if not all_personas:
                # Fallback to dictionary if DB is somehow empty
                persona_name = random.choice(list(PERSONAS.keys()))
                data = PERSONAS[persona_name]
            else:
                persona = random.choice(all_personas)
                persona_name = persona.name
                data = {
                    "name": persona.name,
                    "role": persona.role,
                    "expertise": persona.expertise,
                    "tone": persona.tone
                }
            
            # Persist assignment in lead model
            db_lead = db.get(Lead, lead.id)
            if db_lead:
                db_lead.persona_id = persona_name
                db.commit()
                
        return data

    async def run_opportunity_clustering(self):
        """
        Elite Module 6: Opportunity Clustering Engine.
        Detect multiple similar complaints within the same group.
        Cluster by problem_type.
        Example: buffering complaints, server down, playlist errors.
        CLUSTER TRIGGER: 5 similar complaints within 12 hours.
        """
        now = datetime.utcnow()
        twelve_hours_ago = now - timedelta(hours=12)
        
        with SessionLocal() as db:
            from app.models.message_analysis import MessageAnalysis
            from app.models.message import Message

            # Query for clusters: 5+ complaints in same group within 12 hours
            complaints = db.query(
                Group.id.label("group_id"),
                MessageAnalysis.problem_type,
                func.count(Message.id).label("trigger_count_12h")
            ).join(Message, Message.telegram_group_id == Group.telegram_id)\
             .join(MessageAnalysis, MessageAnalysis.message_id == Message.id)\
             .filter(Message.sent_at >= twelve_hours_ago)\
             .filter(MessageAnalysis.problem_type.isnot(None))\
             .group_by(Group.id, MessageAnalysis.problem_type)\
             .having(func.count(Message.id) >= 5).all()

            for group_id, prob_type, count_12h in complaints:
                logger.info(f"SLIE Elite Opportunity Cluster Detected: {prob_type} in group {group_id} ({count_12h} msgs in 12h)")
                
                # Check if we already handled this cluster recently
                recent_cluster = db.execute(
                    select(OpportunityCluster)
                    .where(
                        and_(
                            OpportunityCluster.group_id == group_id,
                            OpportunityCluster.problem_type == prob_type,
                            OpportunityCluster.timestamp >= twelve_hours_ago
                        )
                    )
                ).scalar_one_or_none()

                if recent_cluster:
                    continue

                # Save trend cluster
                cluster = OpportunityCluster(
                    group_id=group_id,
                    problem_type=prob_type,
                    message_count=count_12h,
                    timestamp=now
                )
                db.add(cluster)
                db.commit()

                # Action: Generate high-authority technical explanation (Module 6 requirement)
                await self.post_authority_explanation(group_id, prob_type)

    async def post_authority_explanation(self, group_id, problem_type):
        """
        Elite Module 6 & 11 Action: Generate authority explanation message in group.
        Uses account rotation and limit tracking (Module 8).
        """
        # Find an account that can perform a public reply (Module 8)
        account = await telegram_client_manager.rotate_account("public_reply")
        if not account:
            logger.warning("No accounts available to post authority explanation.")
            return

        client = await telegram_client_manager.get_client(phone_number=account.phone_number)
        
        # Pick a random persona from the database for the authority post (Module 5)
        self._initialize_personas()
        with SessionLocal() as db:
            import random
            all_personas = db.query(Persona).all()
            if not all_personas:
                # Fallback to dictionary
                persona_name = random.choice(list(PERSONAS.keys()))
                persona_data = PERSONAS[persona_name]
            else:
                persona = random.choice(all_personas)
                persona_data = {
                    "name": persona.name,
                    "role": persona.role,
                    "expertise": persona.expertise,
                    "tone": persona.tone
                }
        
        prompt = f"""
        Generate a high-authority technical explanation for a group of users experiencing {problem_type} in an IPTV group.
        The explanation should be technical, professional, and helpful.
        Example: "Many IPTV outages today appear to be related to overloaded streaming nodes during peak traffic..."
        """
        
        system_prompt = f"""
        You are {persona_data['name']}, {persona_data['role']} for Streamexpert.
        Expertise: {persona_data['expertise']}
        Tone: {persona_data['tone']}
        """
        
        try:
            explanation = await ai_service.chat_completion(
                prompt=prompt,
                system_prompt=system_prompt
            )
            if explanation:
                with SessionLocal() as db:
                    group = db.get(Group, group_id)
                    if group and group.joined:
                        # Simulate human behavior before posting (Module 4 Engine)
                        from app.services.response_engine import response_engine
                        await response_engine.simulate_typing(client, group.telegram_id, delay_range=(10, 20))
                        
                        await client.send_message(group.telegram_id, explanation)
                        
                        # Track account limit (Module 8)
                        await telegram_client_manager.track_account_limits(account.phone_number, "public_reply")
                        
                        logger.info(f"Authority explanation posted by {persona_data['name']} using account {account.phone_number} to {group.name}")
        except Exception as e:
            logger.error(f"Failed to post authority explanation: {e}")

    async def update_group_authority_ranking(self):
        """
        Elite Module 7: Group Authority Ranking Engine.
        Identify which Telegram groups produce the most leads.
        
        METRICS:
        - leads_generated (total leads from this group)
        - conversion_rate (conversions / total leads)
        - activity_level (messages_last_24h)
        
        AUTHORITY SCORE:
        authority_score = (leads_generated * 0.5) + (conversion_rate * 0.3) + (activity_level * 0.2)
        """
        with SessionLocal() as db:
            groups = db.query(Group).all()
            
            for group in groups:
                # 1. leads_generated
                leads_count = db.query(func.count(Lead.id)).filter(Lead.group_id == group.id).scalar() or 0
                
                # 2. conversion_rate (using 100 as base for score calculation)
                conversions = db.query(func.count(Lead.id)).filter(
                    Lead.group_id == group.id,
                    Lead.conversion_stage == ConversionStage.CONVERTED
                ).scalar() or 0
                conv_rate = (conversions / leads_count * 100) if leads_count > 0 else 0
                
                # 3. activity_level
                activity = group.messages_last_24h or 0
                
                # Formula implementation
                score = (leads_count * 0.5) + (conv_rate * 0.3) + (activity * 0.2)
                group.authority_score = int(score)
                
            db.commit()
            logger.info("SLIE Elite: Group authority rankings updated.")

    async def run_trend_detection(self):
        """
        Elite Module 11: Trend Detection Engine.
        Identify spikes in IPTV problem reports (outages/major problems).
        
        PROCESS:
        Monitor problem_type frequency.
        Example: buffering reports > 20 within 2 hours.
        
        ACTION:
        Generate authority explanation post in groups.
        """
        now = datetime.utcnow()
        two_hours_ago = now - timedelta(hours=2)
        
        with SessionLocal() as db:
            from app.models.message_analysis import MessageAnalysis
            from app.models.message import Message

            # 1. Monitor problem_type frequency globally
            trends = db.query(
                MessageAnalysis.problem_type,
                func.count(Message.id).label("occurrence_count")
            ).join(Message, Message.id == MessageAnalysis.message_id)\
             .filter(Message.sent_at >= two_hours_ago)\
             .filter(MessageAnalysis.problem_type.isnot(None))\
             .group_by(MessageAnalysis.problem_type)\
             .having(func.count(Message.id) >= 20).all()

            for prob_type, count in trends:
                logger.info(f"SLIE Elite Trend Detected: {prob_type} spike ({count} reports in 2h)")
                
                # 2. Store trend in database
                trend_record = ProblemTrend(
                    problem_type=prob_type,
                    occurrence_count=count,
                    timestamp=now
                )
                db.add(trend_record)
                db.commit()

                # 3. Identify groups affected by this trend and post explanation
                affected_groups = db.query(Group.id).join(Message, Message.telegram_group_id == Group.telegram_id)\
                    .join(MessageAnalysis, MessageAnalysis.message_id == Message.id)\
                    .filter(Message.sent_at >= two_hours_ago)\
                    .filter(MessageAnalysis.problem_type == prob_type)\
                    .group_by(Group.id).all()

                for (group_id,) in affected_groups:
                    await self.post_authority_explanation(group_id, prob_type)

power_upgrades_service = PowerUpgradesService()
