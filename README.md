# Next.js + Firebase Full-Stack Template

A comprehensive, production-ready template for building full-stack web applications with Next.js frontend and Python Firebase Functions backend.

## 🚀 Features

### Frontend (Next.js)

- 🔐 **Firebase Authentication** - Email/Password, Google Sign-In, Anonymous auth
- 📊 **Firestore Database** - Real-time NoSQL database integration
- 📁 **Firebase Storage** - File upload and management
- 🎨 **Material-UI (MUI)** - Modern React component library
- 🔄 **State Management** - React Context for authentication state
- 🎨 **Form Handling** - React Hook Form with Yup validation
- 📨 **Notifications** - Notistack for user feedback
- 📝 **TypeScript** - Full type safety
- 🚀 **Next.js 14** - React framework with App Router

### Backend (Python Firebase Functions)

- ⚡ **Firebase Functions** - Serverless Python backend
- 🏗️ **Broker Architecture** - Organized function structure
- 📊 **Firestore Integration** - DocumentBase classes for data management
- 🔒 **Authentication** - Built-in auth wrappers and security
- 🧪 **Testing Framework** - Comprehensive test suite with Firebase emulators
- 📦 **Type Safety** - Pydantic models for validation
- 🎯 **TDD Approach** - Test-first development workflow

## 📋 Prerequisites

- Node.js 18+
- Python 3.9+
- Firebase account (sign up at [Firebase Console](https://console.firebase.google.com))
- Firebase CLI (`npm install -g firebase-tools`)

## 🔧 Quick Setup

### 1. Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Click **"Create a project"** or **"Add project"**
3. Enter your project name (e.g., "my-fullstack-app")
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

#### Storage

1. Go to **Storage** > **Get started**
2. Start in test mode
3. Choose the same location as your Firestore database

#### Functions

1. Go to **Functions** > **Get started**
2. Follow the setup instructions

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
cd front

# Install Firebase CLI
npm install -g firebase-tools

# Login to Firebase
firebase login
```

## 🖥️ Frontend Setup (Next.js)

Navigate to the frontend directory and set up:

```bash
cd front

# Install dependencies
npm install
# or
yarn install

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
npm run dev
# or
yarn dev
```

Visit [http://localhost:3000](http://localhost:3000) to see your app.

## 🐍 Backend Setup (Python Firebase Functions)

Navigate to the backend directory and set up:

```bash
cd back

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure your Firebase project (optional but recommended)
python setup.py
```

### Backend Development Workflow

```bash
# Start Firebase emulators (required for development and testing)
firebase emulators:start

# In another terminal, run tests
cd back
source venv/bin/activate  # Activate virtual environment
pytest

# Run with coverage
pytest --cov=src

# Run only integration tests
pytest tests/integration/ -m integration
```

### Deploy Functions

```bash
firebase deploy --only functions
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
│   ├── package.json
│   └── README.md
├── back/                          # Python Firebase Functions Backend
│   ├── main.py                    # Firebase function exports
│   ├── run_tests.py              # Test runner with emulator management
│   ├── requirements.txt           # Python dependencies
│   ├── pytest.ini                # Pytest configuration
│   ├── Makefile                  # Build and deployment commands
│   ├── src/
│   │   ├── apis/                  # Database interfaces and API clients
│   │   │   └── Db.py              # Database singleton with Db
│   │   ├── brokers/
│   │   │   ├── callable/          # Client-callable functions
│   │   │   │   ├── create_item.py
│   │   │   │   ├── get_item.py
│   │   │   │   └── example_callable.py
│   │   │   ├── https/             # HTTP endpoints
│   │   │   │   ├── health_check.py
│   │   │   │   └── webhook_handler.py
│   │   │   └── triggered/         # Event triggers
│   │   │       ├── on_item_created.py
│   │   │       ├── on_item_updated.py
│   │   │       └── on_item_deleted.py
│   │   ├── documents/             # Firestore document classes
│   │   │   ├── DocumentBase.py    # Base document class
│   │   │   ├── items/             # Items collection
│   │   │   │   ├── Item.py        # Document class
│   │   │   │   └── ItemFactory.py # Factory class
│   │   │   └── categories/        # Categories collection
│   │   │       ├── Category.py    # Document class
│   │   │       └── CategoryFactory.py # Factory class
│   │   ├── models/                # Data models and types
│   │   │   ├── firestore_types.py
│   │   │   ├── function_types.py
│   │   │   ├── util_types.py
│   │   │   └── user_types.py
│   │   ├── services/              # Business logic services
│   │   │   └── item_service.py
│   │   ├── util/                  # Utility functions
│   │   │   ├── cors_response.py
│   │   │   ├── db_auth_wrapper.py
│   │   │   └── logger.py
│   │   └── exceptions/            # Custom exceptions
│   │       └── CustomError.py
│   └── tests/
│       ├── conftest.py            # Pytest fixtures
│       ├── integration/           # Integration tests
│       │   └── test_item_flow.py
│       ├── unit/                  # Unit tests
│       └── util/                  # Test utilities
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

## 💻 Development Workflow

### Frontend Development

```bash
cd front

# Start development server
npm run dev

# Build for production
npm run build

# Run linting
npm run lint
```

### Backend Development

```bash
cd back

# Activate virtual environment
source venv/bin/activate

# Run all tests with emulators (recommended)
python run_tests.py

# Run only unit tests (fast)
python run_tests.py --test-type unit --no-emulator

# Run only integration tests
python run_tests.py --test-type integration

# Manual testing alternative
firebase emulators:start  # In one terminal
pytest                    # In another terminal
```

### Full-Stack Development

1. Start Firebase emulators: `firebase emulators:start`
2. In one terminal: `cd front && npm run dev`
3. In another terminal: `cd back && source venv/bin/activate`
4. Test both frontend and backend integration

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

### Environment Configuration

Update the following files with your Firebase project details:

**`back/src/apis/Db.py`** - Update the AppConfiguration class:

```python
def is_prod_environment(self) -> bool:
    return self.project_id in ["your-prod-project-id"]

def is_dev_environment(self) -> bool:
    return self.project_id in ["your-dev-project-id"]
```

## 🧪 Testing

### Backend Testing Principles

1. **Start with integration tests** - Test actual Firebase Functions via HTTP
2. **Test error scenarios first** - Missing params, invalid data, auth failures
3. **Test success scenarios** - Verify both HTTP response AND Firestore documents
4. **Use Firebase emulators** - Never mock Firebase/Firestore operations
5. **Test complete workflows** - End-to-end user journeys

### Example Test Pattern

```python
def test_create_item_success(self, firebase_emulator, setup):
    # Act - Call actual Firebase Function
    response = requests.post(
        f"{firebase_emulator['base_url']}/create_item_callable",
        json={"data": {"name": "Test Item"}},
        headers={"User-Id": setup.user_id}
    )

    # Assert HTTP response
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["success"] is True

    # Assert Firestore document was created correctly
    item = Item(result["itemId"])
    assert item.doc.name == "Test Item"
    assert item.doc.ownerUid == setup.user_id
```

## 🎯 Key Principles

### Backend Architecture

- All Firestore documents must be modified **strictly** within `DocumentBase` classes
- Never make calls to Firestore directly - always use the `Db` class
- Each document type should have its own class extending `DocumentBase`
- Factory classes are co-located with their document classes in collection subfolders

### Type Safety

- All Firestore document types should be defined in `models/firestore_types.py`
- Function request/response types should be defined in `models/function_types.py`
- Use Pydantic models for validation

### Code Organization

- One class per file
- Keep brokers focused on request/response handling
- Business logic belongs in services or document classes
- Factories handle complex object creation

## 📜 Scripts

### Frontend Scripts

```bash
cd front
npm run dev      # Start development server
npm run build    # Build for production
npm run start    # Start production server
npm run lint     # Run ESLint
```

### Backend Scripts

```bash
cd back
make test        # Run tests
make coverage    # Run tests with coverage
make deploy-dev  # Deploy to development
make deploy-prod # Deploy to production
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

### Backend Environment Variables

Required environment variables for Firebase Functions:

- `GCLOUD_PROJECT` - Firebase project ID
- `FIREBASE_CONFIG` - Firebase configuration (auto-set in Functions)
- `SIGNED_URL_SERVICE_ACCOUNT_JSON` - For generating signed URLs (optional)

## 📄 License

MIT

## 🆘 Support

For issues and questions, please open an issue on GitHub.

---

Built with ❤️ using Next.js, Firebase, and Python
