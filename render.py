import base64
import urllib.request
import os

mermaid_code = """graph TD
    START([START]) --> ROLE_CHECK{ROLE CHECK}
    
    ROLE_CHECK -- Admin --> Admin_Start[Admin Flow]
    ROLE_CHECK -- User --> User_Start[User Flow]

    subgraph ADMIN_FLOW [ADMIN FLOW]
        direction TB
        Admin_Start --> AD[Admin Dashboard]
        AD --> MU[Manage Users]
        AD --> VA[View Analytics]
        MU --> AD_DB[(Update Database)]
        VA --> AD_DB
        AD_DB --> END_ADMIN([END])
    end

    subgraph USER_FLOW [USER FLOW]
        direction TB
        User_Start --> HD[Home Dashboard]
        HD --> UPLOAD[Upload Satellite Image]
        UPLOAD --> VAL{Valid Image?}
        VAL -- NO --> UPLOAD
        VAL -- YES --> YOLO[YOLOv8 Detection]
        YOLO --> FEAT[Feature Extraction]
        FEAT --> XAI[XAI Recommendation]
        XAI --> US_DB[(Auto-Save to Database)]
        US_DB --> SHOW[Display Results]
        SHOW --> ACTIONS{User Actions}
        
        ACTIONS --> A1[View Market Prices]
        ACTIONS --> A2[Ask AgriBot]
        ACTIONS --> A3[Download PDF Report]
        ACTIONS --> A4[Change Language]
        
        A1 & A2 & A3 & A4 --> HIST[Home Dashboard / View History]
        HIST --> END_USER([END])
    end

    subgraph ADDITIONAL_MODULES [SYSTEM & SUPPORT MODULES]
        direction LR
        subgraph F_SUB [Additional User Features]
            F["1. Market Analysis<br/>2. Chat with AgriBot<br/>3. Generate Reports<br/>4. Translate Language<br/>5. View History"]
        end
        subgraph S_SUB [Support Modules]
            S["1. Flask Web App<br/>2. SQL Database<br/>3. Deep Learning YOLO<br/>4. XAI Framework"]
        end
    end

    style START fill:#d32f2f,color:#fff,stroke:#fff
    style ROLE_CHECK fill:#ffcc80,color:#000
    style UPLOAD fill:#ffab91,color:#000
    style YOLO fill:#ffab91,color:#000
    style FEAT fill:#ffab91,color:#000
    style XAI fill:#ffcc80,color:#000
    style SHOW fill:#b39ddb,color:#000
    style ACTIONS fill:#b39ddb,color:#000
    style A1 fill:#a5d6a7,color:#000
    style A2 fill:#a5d6a7,color:#000
    style A3 fill:#a5d6a7,color:#000
    style A4 fill:#a5d6a7,color:#000
    style END_USER fill:#d32f2f,color:#fff,stroke:#fff
    style END_ADMIN fill:#d32f2f,color:#fff,stroke:#fff
"""

encoded = base64.b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
url = f"https://mermaid.ink/img/{encoded}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    response = urllib.request.urlopen(req)
    out_path = r"C:\Users\bharg\.gemini\antigravity\brain\71d69bff-4d04-4823-b42e-ab93d7f2f2a4\workflow_final.png"
    with open(out_path, 'wb') as f:
        f.write(response.read())
    print("Saved to", out_path)
except Exception as e:
    print("Error:", e)
    print("URL length:", len(url))
