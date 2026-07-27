  # Non-blocking celery task
    ┌─────────────────────────────────────────────────────────────────┐
  │                        DATABASE (Shared State)                  │
  │                                                                 │
  │  BackgroundTask Table:                                         │
  │  ┌──────────────────────────────────────────────────────────┐ │
  │  │ id (UUID)           | user_id | task_type | status        │ │
  │  │ result (JSON TEXT)  | error   | created_at | completed_at │ │
  │  └──────────────────────────────────────────────────────────┘ │
  │         ↑ WRITE (create)                  ↑ WRITE (update)    │
  │         │                                  │                   │
  │    ┌────┴─────┐                      ┌────┴─────┐            │
  │    │  FLASK   │                      │  CELERY  │            │
  │    │   APP    │                      │  WORKER  │            │
  │    └──────────┘                      └──────────┘            │
  └─────────────────────────────────────────────────────────────────┘
  
  Flask App (creates)          Celery Worker (updates)
       ↓                              ↓
  BackgroundTask DB Record ← shared → BackgroundTask DB Record

  Step-by-step:
  1. Flask creates BackgroundTask record: status='pending', result=NULL
  2. Flask passes task_id to Celery and returns immediately
  3. Celery fetches the same record: BackgroundTask.query.get(task_id)
  4. Celery updates: status='running', then status='completed', result='{"analysis": ...}'
  5. Flask polls the record to check status and retrieve results



# UI Schema

For UI Layer:

  {
    "visualization_data": {
      "kpis": {
        "win_rate": 45,
        "market_avg": 52,
        "avg_hold_winners": 4,
        "avg_hold_losers": 18,
        "fomo_rate": 23,
        "risk_level": "MEDIUM"
      },
      "behavioral_patterns": [
        {
          "pattern_name": "Disposition Effect",
          "severity": "HIGH",
          "description": "...",
          "evidence_trades": ["AMR: ...", "1D3.F: ..."],
          "recommendation": "Set exit criteria before buying"
        }
      ],
      "evolution_timeline": [
        {
          "period": "2020-2021",
          "phase_name": "Exploration",
          "key_metrics": {"trades": 15, "avg_return": -5},
          "lessons": ["Started averaging down"]
        }
      ],
      "fomo_trades": [...]
    }
  }

  For Intelligence Layer:

  {
    "intelligence_data": {
      "pattern_metadata": {
        "disposition_effect": {
          "severity_score": 0.85,
          "affected_stocks": ["1D3.F", "INL.F", "AMR"],
          "loser_hold_avg": 730,
          "winner_hold_avg": 60
        }
      },
      "research_correlation_hints": {
        "stocks_needing_check": ["1D3.F", "AMR"],
        "check_criteria": ["exit_criteria", "thesis_updates", "checklist_completion"]
      },
      "learning_patterns": {
        "repeating_mistakes": ["penny_stock_speculation", "averaging_down"],
        "success_factors": ["momentum_capture", "quick_profits"]
      }
    }
  }




