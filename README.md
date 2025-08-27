# Next.js + Firebase Full-Stack Template with AI-First Development

A production-ready template featuring event-driven broker architecture, designed for rapid AI-assisted development. Build full-stack applications with Next.js frontend and Python Firebase Functions backend using parallel AI agents.

## 🚀 Key Features

### Architecture & Development
- 🤖 **AI-First Development** - Optimized for multi-agent parallel development
- 📊 **Event-Driven Architecture** - Database as single source of truth
- 📝 **Built-in AI Rules** - PRD, ADR, and task templates for AI agents
- 🔄 **Real-time Updates** - Firestore subscriptions for automatic UI updates

### Frontend (Next.js)
- 🔐 **Firebase Authentication** - Email/Password & Google Sign-In
- 📊 **Firestore Database** - Real-time NoSQL with subscription hooks
- 📁 **Firebase Storage** - File upload and management
- 🎨 **Material-UI (MUI)** - Modern React components
- 🔄 **State Management** - React Context for auth
- 📝 **TypeScript** - Full type safety
- 🚀 **Next.js 14** - App Router with server components

### Backend (Python Firebase Functions)
- ⚡ **Serverless Functions** - Auto-scaling Python backend
- 🏗️ **Broker Architecture** - Event-driven, decoupled design
- 📊 **DocumentBase Classes** - Structured Firestore management
- 🔒 **Authentication Wrappers** - Built-in security
- 🧪 **Integration Testing** - Real API testing with emulators
- 📦 **Pydantic Models** - Runtime validation
- 🎯 **TDD Workflow** - Test-first development

## 📋 Prerequisites

- Node.js 18+
- Python 3.9+
- Firebase account (sign up at [Firebase Console](https://console.firebase.google.com))
- Firebase CLI (`npm install -g firebase-tools`)

## 🔧 Quick Setup

### 1. Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Click **"Create a project"** or **"Add project"**
3. Enter your project name
4. Choose whether to enable Google Analytics (optional)
5. Wait for the project to be created

### 2. Enable Firebase Services

#### Authentication

1. Go to **Authentication** > **Sign-in method**
2. Enable **Email/Password** provider
3. Enable **Google** provider (optional but recommended)

#### Firestore Database

1. Go to **Firestore Database** > **Create database**
2. Choose **Start in test mode** for development
3. Select a location closest to your users
4. Note: You'll secure it with rules before production

#### Storage

1. Go to **Storage** > **Get started**
2. Start in test mode
3. Choose the same location as your Firestore database

#### Functions

1. Go to **Functions** > **Get started**
2. **Note**: Requires Blaze (Pay as you go) plan
   - Firebase has generous free tiers
   - Required for Functions and advanced features
3. Follow the setup instructions

### 3. Get Firebase Configuration

1. In your Firebase project, click **⚙️** > **Project settings**
2. Scroll to **"Your apps"** section
3. Click **Web** icon `</>`
4. Register your app with a nickname
5. Copy the Firebase configuration object

### 4. Clone and Setup Project

```bash
# Clone the repository
git clone <your-repo-url>
cd <project-directory>

# Install Firebase CLI globally
npm install -g firebase-tools

# Login to Firebase
firebase login

# Configure Firebase project
# Edit .firebaserc and replace with your project ID
```

## 🖥️ Frontend Setup (Next.js)

Navigate to the frontend directory:

```bash
cd front

# Install dependencies
yarn install
# or
npm install

# Create environment file
cp .env.example .env.local
```

### Environment Configuration

Open `front/.env.local` and add your Firebase configuration:

```env
NEXT_PUBLIC_FIREBASE_API_KEY=your_api_key_here
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project-id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=123456789
NEXT_PUBLIC_FIREBASE_APP_ID=1:123456789:web:abcdef
NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX
```

### Run Frontend Development Server

```bash
yarn dev
# or
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to see your app.

## 🐍 Backend Setup (Python Firebase Functions)

### Setup Python Environment

```bash
cd back

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure Service Account

1. Go to Firebase Console > Project Settings > Service Accounts
2. Click "Generate new private key" and download the JSON file
3. Place the JSON file in the `back/` directory
4. Create `.env` file in `back/` directory:

```bash
cp .env.example .env
# Edit .env and add:
# FIREBASE_SERVICE_ACCOUNT_PATH=./your-service-account-key.json
# Add any other API keys your project needs
```

### Backend Development Workflow

```bash
# Start Firebase emulators (required for testing)
firebase emulators:start

# In another terminal, run tests
cd back
source venv/bin/activate

# Run all tests with emulators (recommended)
python run_tests.py

# Run only unit tests (fast, no emulator needed)
python run_tests.py --test-type unit --no-emulator

# Run only integration tests
python run_tests.py --test-type integration

# Manual testing with pytest
pytest  # Ensure emulators are running first
```

### Deploy Functions

```bash
# Deploy functions only
firebase deploy --only functions

# Deploy security rules
firebase deploy --only firestore:rules,storage:rules

# Deploy everything
firebase deploy
```

## 📁 Project Structure

```
nextjs-firebase-ai-coding-template/
├── front/                         # Next.js Frontend
│   ├── src/
│   │   ├── app/                   # Next.js app router pages
│   │   │   ├── layout.tsx         # Root layout
│   │   │   ├── page.tsx           # Home page
│   │   │   ├── signin/            # Sign in page
│   │   │   ├── signup/            # Sign up page
│   │   │   └── dashboard/         # Protected dashboard
│   │   ├── auth/                  # Authentication logic
│   │   │   ├── authContext.ts     # Auth context definition
│   │   │   ├── authOperations.ts  # Auth functions
│   │   │   ├── AuthProvider.tsx   # Auth context provider
│   │   │   └── useAuth.ts         # Auth hook
│   │   ├── lib/                   # Firebase services
│   │   │   ├── firebase.ts        # Firebase initialization
│   │   │   ├── firestore.ts       # Firestore operations
│   │   │   ├── functions.ts       # Cloud Functions
│   │   │   └── storage.ts         # Storage operations
│   │   ├── theme/                 # MUI theme configuration
│   │   └── config.ts              # App configuration
│   ├── .env.example              # Environment variables template
│   ├── package.json
│   └── FRONTEND_RULES.md         # Frontend-specific AI rules
├── back/                          # Python Firebase Functions Backend
│   ├── main.py                    # Firebase function exports
│   ├── run_tests.py              # Test runner with emulator management
│   ├── requirements.txt           # Python dependencies
│   ├── pytest.ini                # Pytest configuration
│   ├── .env.example              # Backend environment template
│   ├── BACKEND_RULES.md         # Backend-specific AI rules
│   ├── ADR.md                    # Architecture Decision Records
│   ├── src/
│   │   ├── apis/                  # Database interfaces and API clients
│   │   │   └── Db.py              # Database singleton
│   │   ├── brokers/               # Firebase function handlers
│   │   │   ├── callable/          # Client-callable functions
│   │   │   ├── https/             # HTTP endpoints
│   │   │   └── triggered/         # Event-triggered functions
│   │   ├── documents/             # Firestore document classes
│   │   │   ├── DocumentBase.py    # Base document class
│   │   │   └── [collections]/     # Collection-specific classes
│   │   ├── models/                # Data models and types
│   │   │   ├── firestore_types.py # Firestore document types
│   │   │   ├── function_types.py  # Function request/response types
│   │   │   └── util_types.py      # Utility types
│   │   ├── services/              # Business logic services
│   │   ├── util/                  # Utility functions
│   │   └── exceptions/            # Custom exceptions
│   └── tests/
│       ├── conftest.py            # Pytest fixtures
│       ├── integration/           # Integration tests
│       └── unit/                  # Unit tests
├── tasks/                         # AI Development Templates
│   ├── PRD.md                    # Product Requirements Document template
│   └── TASK_TEMPLATE.md          # Task breakdown template
├── AGENTS.md                     # AI agent instructions
├── firebase.json                  # Firebase configuration
├── firestore.rules               # Firestore security rules
├── storage.rules                 # Storage security rules
└── README.md                     # This file
```

## 🔐 Security Rules

### Firestore Rules

Update `firestore.rules` with appropriate security rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow users to read/write their own documents
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

### Storage Rules

Update `storage.rules` for file security:

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /users/{userId}/{allPaths=**} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

## 🤖 AI-Assisted Development Workflow

### 1. Project Scoping (GPT-4o or similar)

```bash
# Generate PRD from requirements
# Use tasks/PRD.md template
# Ask AI to interview you until it can fill the PRD

# Break down into tasks
# Use tasks/TASK_TEMPLATE.md
# Have AI create specific, actionable tasks with dependencies
```

### 2. Parallel Agent Development

Launch multiple AI agents (Cursor, Claude Code, etc.) in parallel:

```bash
# Agent 1: Frontend auth
@AGENTS.md @FRONTEND_RULES.md implement [task1.md]

# Agent 2: Backend API
@AGENTS.md @BACKEND_RULES.md implement [task2.md]

# Agent 3: Database models
@AGENTS.md @BACKEND_RULES.md implement [task3.md]

# Agent 4: Integration tests
@AGENTS.md implement integration tests for [feature]
```

### 3. Testing Workflow

```bash
# Backend: Always write integration tests first
cd back
source venv/bin/activate
python run_tests.py  # Tests with real APIs

# Frontend: Test with emulators
firebase emulators:start
cd front && yarn dev
```

### 4. Documentation

After significant changes, update ADR:

```bash
# Tell agent to document decisions
"Document the key architectural decisions in back/ADR.md"
```

## 💻 Traditional Development Workflow

### Frontend Development

```bash
cd front
yarn dev          # Start development server
yarn build        # Build for production
yarn lint         # Run linting
```

### Backend Development

```bash
cd back
source venv/bin/activate

# Run tests
python run_tests.py                    # All tests with emulators
python run_tests.py --test-type unit   # Unit tests only
python run_tests.py --test-type integration  # Integration tests only
```

### Full-Stack Development

1. Start Firebase emulators: `firebase emulators:start`
2. Frontend terminal: `cd front && yarn dev`
3. Backend terminal: `cd back && source venv/bin/activate`
4. Make changes and test integration

## 📚 Usage Examples

### Frontend Authentication

```typescript
import { useAuth } from "@/auth/useAuth";
import { authOperations } from "@/auth/authOperations";

// Using the auth hook
function MyComponent() {
  const { user, loading, isAuthenticated } = useAuth();

  if (loading) return <div>Loading...</div>;
  if (!isAuthenticated) return <div>Please sign in</div>;

  return <div>Welcome, {user.email}!</div>;
}

// Auth operations
await authOperations.signUp(email, password, displayName);
await authOperations.signIn(email, password);
await authOperations.signInWithGoogle();
await authOperations.signOut();
```

### Frontend Firestore Operations

```typescript
import { userOperations } from "@/lib/firestore";

// Create user document
await userOperations.create(uid, { displayName, email });

// Get user by ID
const user = await userOperations.getById(uid);

// Update user
await userOperations.update(uid, { displayName: "New Name" });
```

### Backend Callable Functions

```python
# src/brokers/callable/example_callable.py
from firebase_functions import https_fn, options
from src.apis.Db import Db
from src.util.db_auth_wrapper import db_auth_wrapper

@https_fn.on_call(
    cors=options.CorsOptions(cors_origins=["*"]),
    ingress=options.IngressSetting.ALLOW_ALL,
)
def example_callable(req: https_fn.CallableRequest):
    uid = db_auth_wrapper(req)
    # Implementation
```

### Backend Document Classes

```python
# src/documents/examples/Example.py
from src.documents.DocumentBase import DocumentBase
from src.apis.Db import Db
from src.models.firestore_types import ExampleDoc

class Example(DocumentBase[ExampleDoc]):
    pydantic_model = ExampleDoc

    def __init__(self, id: str, doc: Optional[dict] = None):
        self._db = Db.get_instance()
        self.collection_ref = self.db.collections["examples"]
        super().__init__(id, doc)

    @property
    def db(self) -> Db:
        if self._db is None:
            self._db = Db.get_instance()
        return self._db
```

## 🚀 Deployment

### Frontend Deployment (Vercel)

1. Push your code to GitHub
2. Import your repository on [Vercel](https://vercel.com)
3. Add environment variables in Vercel dashboard
4. Deploy!

### Backend Deployment (Firebase Functions)

```bash
cd back

firebase deploy --only functions
```

### Production Configuration

1. **Update Project IDs** in `back/src/apis/Db.py`:

```python
def is_prod_environment(self) -> bool:
    return self.project_id in ["your-prod-project-id"]

def is_dev_environment(self) -> bool:
    return self.project_id in ["your-dev-project-id"]
```

2. **Deploy Security Rules**:

```bash
# Review and customize rules first
cat firestore.rules
cat storage.rules

# Deploy rules
firebase deploy --only firestore:rules,storage:rules
```

3. **Set Firebase Indexes** (if needed):
- Check console for index requirements
- Click provided links to create indexes

## 🧪 Testing Strategy

### Testing Philosophy

1. **Integration First** - Test real Firebase Functions, not mocks
2. **Error Cases First** - Test failure scenarios before success
3. **Full Verification** - Check both API responses and database state
4. **Use Emulators** - Never mock Firebase services
5. **End-to-End** - Test complete user workflows

### AI Testing Guidelines

When working with AI agents:

```bash
# Always tell AI to:
1. Write integration tests with real data
2. Run tests and verify they pass
3. Test with actual files/APIs, not mocks
4. Show you where to find generated outputs
```

### Example Test Pattern

```python
def test_feature_integration(self, firebase_emulator, setup):
    # Arrange - Prepare test data
    test_data = {"field": "value"}
    
    # Act - Call real Firebase Function
    response = requests.post(
        f"{firebase_emulator['base_url']}/function_name",
        json={"data": test_data},
        headers={"User-Id": setup.user_id}
    )

    # Assert - Verify response
    assert response.status_code == 200
    result = response.json()["result"]
    
    # Assert - Verify database state
    doc = DocumentClass(result["docId"])
    assert doc.exists
    assert doc.data.field == "value"
```

## 🎯 Architecture Principles

### Event-Driven Broker Architecture

- **Database as Truth** - Firestore is the single source of truth
- **No Direct Responses** - Backend saves to DB, frontend subscribes
- **Real-time Updates** - UI updates automatically via Firestore hooks
- **Decoupled Design** - Frontend and backend communicate through database

### Backend Principles

- **DocumentBase Pattern** - All Firestore operations through DocumentBase classes
- **No Direct DB Calls** - Always use the Db singleton
- **One Class Per File** - Maintain clear file organization
- **Broker Pattern** - Handlers stay thin, logic in services

### Type Safety

- **Pydantic Models** - Define all types in models/
- **Runtime Validation** - Catch errors early
- **Type as Documentation** - Types serve as API contracts

### AI Development Principles

- **Parallel Agents** - Run multiple agents simultaneously
- **Test-Driven** - AI must write and run tests
- **Documentation** - Update ADR after major decisions
- **Real APIs** - Never let AI mock critical services

## 📜 Available Commands

### Frontend Commands

```bash
cd front
yarn dev         # Start development server
yarn build       # Build for production
yarn start       # Start production server
yarn lint        # Run ESLint
yarn type-check  # Run TypeScript checks
```

### Backend Commands

```bash
cd back
python run_tests.py              # Run all tests with emulators
python run_tests.py --test-type unit  # Unit tests only
python run_tests.py --test-type integration  # Integration tests
pytest --cov=src                 # Run with coverage report
```

### Firebase Commands

```bash
firebase emulators:start         # Start local emulators
firebase deploy                  # Deploy everything
firebase deploy --only functions # Deploy functions only
firebase deploy --only hosting   # Deploy frontend only
firebase deploy --only firestore:rules  # Deploy Firestore rules
```

## 🔧 Environment Variables

### Frontend (front/.env.local)

```env
NEXT_PUBLIC_FIREBASE_API_KEY=your_api_key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_auth_domain
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your_storage_bucket
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your_messaging_sender_id
NEXT_PUBLIC_FIREBASE_APP_ID=your_app_id
NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=your_measurement_id
```

### Environment Variables

**Backend (`back/.env`)**:
- `FIREBASE_SERVICE_ACCOUNT_PATH` - Path to service account JSON
- `[YOUR_API_KEYS]` - Any third-party API keys needed

**Frontend (`front/.env.local`)**:
- All `NEXT_PUBLIC_FIREBASE_*` variables from Firebase config
- Any other public environment variables

**Note**: Never commit `.env` files or service account keys to version control!

## 🚀 Quick Start Checklist

- [ ] Create Firebase project
- [ ] Enable Authentication, Firestore, Storage, Functions
- [ ] Download service account key
- [ ] Configure environment variables
- [ ] Install dependencies (front & back)
- [ ] Start emulators
- [ ] Run tests
- [ ] Launch development servers
- [ ] Create PRD with AI
- [ ] Generate tasks from PRD
- [ ] Launch parallel AI agents

## 📚 Resources

- [Firebase Documentation](https://firebase.google.com/docs)
- [Next.js Documentation](https://nextjs.org/docs)
- [Cursor AI Editor](https://cursor.sh)
- [Claude Code](https://claude.ai/code)

## 🆘 Support

For issues and questions, please open an issue on GitHub.

---

Built for the AI development era with Next.js, Firebase, and Python
