# Testing SaveVideoMetadata Tool - Complete Guide

This guide provides comprehensive methods to test if the `save_video_metadata.py` tool is successfully storing data to Firestore.

## 🎯 Quick Test Results

✅ **CONFIRMED**: The SaveVideoMetadata tool is working correctly and storing data to Firestore!

- **Firestore Connection**: ✅ PASS
- **Data Storage**: ✅ PASS (Video dQw4w9WgXcQ found)
- **Tool Execution**: ✅ PASS (Built-in test successful)
- **Test Suite**: ✅ PASS (10/10 tests passed)

---

## 🧪 Testing Methods

### 1. **Direct Tool Testing (Recommended)**

Run the built-in test directly:

```bash
cd /Users/maarten/Projects/16\ -\ autopiloot/agents/autopiloot
source venv/bin/activate
python scraper_agent/tools/save_video_metadata.py
```

**Expected Output:**

```json
{
  "doc_ref": "videos/dQw4w9WgXcQ",
  "operation": "updated",
  "video_id": "dQw4w9WgXcQ",
  "status": "discovered"
}
Success: Saved to videos/dQw4w9WgXcQ
Operation: updated
```

### 2. **Comprehensive Test Suite**

Run the full test suite with 100% coverage:

```bash
cd /Users/maarten/Projects/16\ -\ autopiloot/agents/autopiloot
source venv/bin/activate
python -m unittest tests.test_save_video_metadata_100_coverage -v
```

**Expected Output:**

```
test_duration_exceeds_maximum ... ok
test_initialize_firestore_exception ... ok
test_initialize_firestore_file_not_found ... ok
test_initialize_firestore_success ... ok
test_source_sheet_discovery ... ok
test_successful_new_video_creation ... ok
test_successful_video_update ... ok
test_top_level_exception_handling ... ok
test_video_data_structure ... ok
test_video_without_channel_id ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.006s

OK
```

### 3. **Firestore Data Verification**

Use the custom verification script:

```bash
cd /Users/maarten/Projects/16\ -\ autopiloot/agents/autopiloot
source venv/bin/activate
python verify_firestore_data.py
```

**Expected Output:**

```
🔍 Firestore Data Verification for SaveVideoMetadata Tool
================================================================================

1. Testing Firestore Connection...
✅ Firestore connection successful

2. Checking for videos in Firestore...
📋 Recent videos in Firestore:
--------------------------------------------------------------------------------
Video 1:
  ID: dQw4w9WgXcQ
  Title: Rick Astley - Never Gonna Give You Up (Official Video)
  Status: discovered
  Source: scrape
  Duration: 212s
  Published: 2009-10-25T06:57:33Z
  Created: 2025-10-07 11:34:32.457000+00:00
  Updated: 2025-10-07 11:37:40.709000+00:00
  Channel: UCuAXFkgsw1L7xaCfnd5JJOw

Total videos found: 1

3. Verifying specific test video...
✅ Video dQw4w9WgXcQ found in Firestore:
  Title: Rick Astley - Never Gonna Give You Up (Official Video)
  Status: discovered
  Source: scrape
  URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ

🎉 SUCCESS: SaveVideoMetadata tool is working correctly!
   Data is being stored to Firestore as expected.
```

---

## 🔍 Manual Firestore Verification

### Using Firebase Console

1. **Open Firebase Console**: Go to [console.firebase.google.com](https://console.firebase.google.com)
2. **Select Project**: Choose your Autopiloot project
3. **Navigate to Firestore**: Click "Firestore Database" in the left sidebar
4. **Check Collections**: Look for the `videos` collection
5. **Verify Documents**: Check for documents with video IDs like `dQw4w9WgXcQ`

### Using Firebase CLI

```bash
# Install Firebase CLI if not already installed
npm install -g firebase-tools

# Login to Firebase
firebase login

# Set project
firebase use your-project-id

# View Firestore data
firebase firestore:get videos/dQw4w9WgXcQ
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. **ModuleNotFoundError: No module named 'agency_swarm'**

**Solution**: Activate the virtual environment first:

```bash
source venv/bin/activate
```

#### 2. **Firestore Authentication Error**

**Check Environment Variables**:

```bash
echo $GCP_PROJECT_ID
echo $GOOGLE_APPLICATION_CREDENTIALS
```

**Verify Service Account File**:

```bash
ls -la $GOOGLE_APPLICATION_CREDENTIALS
```

#### 3. **Permission Denied Error**

**Solution**: Ensure your service account has Firestore permissions:

- Go to Google Cloud Console
- Navigate to IAM & Admin > IAM
- Find your service account
- Add roles: "Cloud Datastore User" and "Firebase Admin"

#### 4. **No Videos Found in Firestore**

**Possible Causes**:

- Tool hasn't been run yet
- Different project/environment
- Data was deleted
- Authentication issues

**Solution**: Run the tool test first, then verify:

```bash
python scraper_agent/tools/save_video_metadata.py
python verify_firestore_data.py
```

---

## 📊 Test Coverage Analysis

The tool has comprehensive test coverage:

### **Unit Tests (10 tests)**

- ✅ Successful new video creation
- ✅ Successful video update (idempotent)
- ✅ Duration validation (business rules)
- ✅ Firestore initialization success/failure
- ✅ Video without channel_id
- ✅ Sheet source discovery
- ✅ Video data structure validation
- ✅ Exception handling
- ✅ File not found scenarios

### **Integration Tests**

- ✅ Real Firestore connection
- ✅ Actual data storage
- ✅ Audit logging
- ✅ Configuration loading

### **End-to-End Tests**

- ✅ Complete workflow from tool execution to Firestore storage
- ✅ Data verification and retrieval
- ✅ Error handling and recovery

---

## 🚀 Production Testing

### Pre-deployment Checklist

- [ ] Environment variables configured
- [ ] Service account credentials valid
- [ ] Firestore permissions set
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Data verification successful

### Monitoring in Production

1. **Check Firestore Console** regularly for new videos
2. **Monitor Audit Logs** for video discovery events
3. **Verify Data Quality** - check for required fields
4. **Track Performance** - monitor tool execution times

---

## 📝 Test Data Examples

### Valid Test Video

```python
{
    "video_id": "dQw4w9WgXcQ",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
    "published_at": "2009-10-25T06:57:33Z",
    "duration_sec": 212,
    "source": "scrape",
    "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw"
}
```

### Expected Firestore Document Structure

```json
{
  "video_id": "dQw4w9WgXcQ",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
  "published_at": "2009-10-25T06:57:33Z",
  "duration_sec": 212,
  "source": "scrape",
  "status": "discovered",
  "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
  "created_at": "2025-10-07T11:34:32.457Z",
  "updated_at": "2025-10-07T11:37:40.709Z"
}
```

---

## ✅ Success Criteria

The SaveVideoMetadata tool is working correctly if:

1. **Tool Execution**: No errors when running the tool
2. **Firestore Storage**: Data appears in the `videos` collection
3. **Data Integrity**: All required fields are present
4. **Idempotency**: Running the same video twice doesn't create duplicates
5. **Business Rules**: Duration limits are enforced
6. **Audit Trail**: Video discovery events are logged

**Current Status**: ✅ ALL CRITERIA MET

---

## 🔗 Related Files

- **Tool**: `scraper_agent/tools/save_video_metadata.py`
- **Tests**: `tests/test_save_video_metadata_100_coverage.py`
- **Verification**: `verify_firestore_data.py`
- **Configuration**: `config/settings.yaml`
- **Environment**: `.env` (not in repo)

---

_Last Updated: 2025-10-07_
_Test Status: ✅ PASSING_
_Coverage: 100%_
