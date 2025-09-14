import os
import json
from typing import Dict, Any
from datetime import datetime, timedelta
from google.cloud import firestore
from slack_sdk import WebClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class MonitorTranscriptionBudget(BaseTool):
    def __init__(self):
        super().__init__()
        self.db = self._initialize_firestore()
        self.slack = WebClient(token=self.slack_token) if self.slack_token else None
    
    def _validate_env_vars(self):
        self.service_account_path = self.get_env_var("GOOGLE_SERVICE_ACCOUNT_PATH")
        self.project_id = self.get_env_var("GCP_PROJECT_ID")
        self.daily_budget_usd = float(self.get_env_var("TRANSCRIPTION_DAILY_BUDGET_USD", required=False) or "5.0")
        self.alert_threshold = float(self.get_env_var("BUDGET_ALERT_THRESHOLD", required=False) or "0.8")
        self.slack_token = self.get_env_var("SLACK_BOT_TOKEN", required=False)
        self.slack_channel = self.get_env_var("SLACK_ALERTS_CHANNEL", required=False) or "#alerts"
    
    def _initialize_firestore(self):
        return firestore.Client(
            project=self.project_id,
            credentials=None
        )
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        date = request.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
        
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            start_of_day = datetime.combine(date_obj.date(), datetime.min.time())
            end_of_day = start_of_day + timedelta(days=1)
            
            transcripts_ref = self.db.collection('transcripts')
            query = transcripts_ref.where('created_at', '>=', start_of_day).where('created_at', '<', end_of_day)
            
            total_cost = 0.0
            transaction_count = 0
            
            for doc in query.stream():
                data = doc.to_dict()
                costs = data.get('costs', {})
                transcription_cost = costs.get('transcription_usd', 0)
                total_cost += transcription_cost
                transaction_count += 1
            
            costs_daily_ref = self.db.collection('costs_daily').document(date)
            costs_daily_ref.set({
                'date': date,
                'transcription_usd': total_cost,
                'transaction_count': transaction_count,
                'budget_usd': self.daily_budget_usd,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            
            budget_percentage = (total_cost / self.daily_budget_usd) * 100 if self.daily_budget_usd > 0 else 0
            
            if budget_percentage >= (self.alert_threshold * 100):
                alert_message = f"⚠️ *Transcription Budget Alert*\n\n"
                alert_message += f"Date: {date}\n"
                alert_message += f"Spent: ${total_cost:.2f} ({budget_percentage:.1f}%)\n"
                alert_message += f"Budget: ${self.daily_budget_usd:.2f}\n"
                alert_message += f"Transactions: {transaction_count}"
                
                if self.slack and self.slack_channel:
                    try:
                        self.slack.chat_postMessage(
                            channel=self.slack_channel,
                            blocks=[
                                {
                                    "type": "header",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "⚠️ Transcription Budget Alert"
                                    }
                                },
                                {
                                    "type": "section",
                                    "fields": [
                                        {"type": "mrkdwn", "text": f"*Date:*\n{date}"},
                                        {"type": "mrkdwn", "text": f"*Spent:*\n${total_cost:.2f}"},
                                        {"type": "mrkdwn", "text": f"*Budget:*\n${self.daily_budget_usd:.2f}"},
                                        {"type": "mrkdwn", "text": f"*Usage:*\n{budget_percentage:.1f}%"},
                                        {"type": "mrkdwn", "text": f"*Transactions:*\n{transaction_count}"}
                                    ]
                                },
                                {
                                    "type": "context",
                                    "elements": [
                                        {
                                            "type": "mrkdwn",
                                            "text": f"Alert threshold: {self.alert_threshold * 100:.0f}%"
                                        }
                                    ]
                                }
                            ]
                        )
                    except Exception as e:
                        print(f"Failed to send Slack alert: {str(e)}")
                
                return {
                    "status": "alert_sent",
                    "total_cost_usd": total_cost,
                    "budget_percentage": budget_percentage,
                    "transaction_count": transaction_count
                }
            
            return {
                "status": "within_budget",
                "total_cost_usd": total_cost,
                "budget_percentage": budget_percentage,
                "transaction_count": transaction_count
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to monitor transcription budget: {str(e)}")


if __name__ == "__main__":
    tool = MonitorTranscriptionBudget()
    
    test_request = {
        "date": datetime.utcnow().strftime('%Y-%m-%d')
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {result['status']}")
        print(f"Total cost: ${result['total_cost_usd']:.2f}")
        print(f"Budget usage: {result['budget_percentage']:.1f}%")
        print(f"Transactions: {result['transaction_count']}")
    except Exception as e:
        print(f"Error: {str(e)}")