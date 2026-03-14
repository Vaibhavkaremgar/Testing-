# Pagination Implementation Guide

## ✅ Backend Changes (COMPLETED)

### 1. Updated API Endpoints

All endpoints now support `page` and `limit` parameters instead of `skip`:

#### Candidates API (`/api/candidates`)
- **Parameters**: `page=1`, `limit=10` (default: 10 records per page)
- **Count Endpoint**: `/api/candidates/count` - Returns total count with same filters

#### Jobs API (`/api/jobs`)
- **Parameters**: `page=1`, `limit=10` (default: 10 records per page)
- **Count Endpoint**: `/api/jobs/count` - Returns total count with same filters

#### Interviews API (`/api/interviews`)
- **Parameters**: `page=1`, `limit=10` (default: 10 records per page)
- **Count Endpoint**: `/api/interviews/count` - Returns total count with same filters

#### Clients API (`/api/clients`)
- **Parameters**: `page=1`, `limit=10` (default: 10 records per page)
- **Count Endpoint**: `/api/clients/count` - Returns total count

### 2. API Client Updates (`frontend/src/lib/api.js`)

Added count methods for all resources:
```javascript
api.getCandidatesCount(params)
api.getJobsCount(params)
api.getInterviewsCount(params)
api.getClientsCount(params)
```

## 📋 Frontend Implementation Steps

### Step 1: Add Pagination State to Each Page

```javascript
const [currentPage, setCurrentPage] = useState(1)
const [totalRecords, setTotalRecords] = useState(0)
const ITEMS_PER_PAGE = 10
```

### Step 2: Update Fetch Function

```javascript
const fetchData = async () => {
  try {
    // Fetch records for current page
    const params = {
      page: currentPage,
      limit: ITEMS_PER_PAGE,
      // ... other filters
    }
    const data = await api.getRecords(params)
    setRecords(data)
    
    // Fetch total count
    const countData = await api.getRecordsCount(params)
    setTotalRecords(countData.total)
  } catch (error) {
    console.error('Failed to fetch data:', error)
  }
}
```

### Step 3: Reset Page on Filter Changes

```javascript
useEffect(() => {
  setCurrentPage(1) // Reset to page 1 when filters change
}, [search, filterValue, selectedOption])
```

### Step 4: Add Pagination Component

```javascript
import { Pagination } from '@/components/ui/pagination'

// In your JSX, after the table:
<Pagination
  currentPage={currentPage}
  totalPages={Math.ceil(totalRecords / ITEMS_PER_PAGE)}
  totalItems={totalRecords}
  itemsPerPage={ITEMS_PER_PAGE}
  onPageChange={setCurrentPage}
/>
```

## 🎯 Pages to Update

### 1. Resumes.jsx ✅ (ALREADY IMPLEMENTED)
- ✅ Pagination state added
- ✅ Fetch with page/limit
- ✅ Count endpoint integrated
- ✅ Pagination component added
- ✅ Reset page on filter changes

### 2. Jobs.jsx (NEEDS UPDATE)
**Current**: Fetches all jobs at once
**Required Changes**:
```javascript
// Add state
const [currentPage, setCurrentPage] = useState(1)
const [totalJobs, setTotalJobs] = useState(0)
const ITEMS_PER_PAGE = 10

// Update fetchJobs
const fetchJobs = async () => {
  const params = { page: currentPage, limit: ITEMS_PER_PAGE }
  if (selectedClient) params.client = selectedClient
  
  const [jobsData, countData] = await Promise.all([
    api.getJobs(params),
    api.getJobsCount(params)
  ])
  setJobs(jobsData)
  setTotalJobs(countData.total)
}

// Reset page on client filter change
useEffect(() => {
  setCurrentPage(1)
}, [selectedClient])

// Add pagination component after job cards
<Pagination
  currentPage={currentPage}
  totalPages={Math.ceil(totalJobs / ITEMS_PER_PAGE)}
  totalItems={totalJobs}
  itemsPerPage={ITEMS_PER_PAGE}
  onPageChange={setCurrentPage}
/>
```

### 3. Clients.jsx (NEEDS UPDATE)
**Current**: Fetches all clients at once
**Required Changes**:
```javascript
// Add state
const [currentPage, setCurrentPage] = useState(1)
const [totalClients, setTotalClients] = useState(0)
const ITEMS_PER_PAGE = 10

// Update fetchData
const fetchData = async () => {
  const params = { page: currentPage, limit: ITEMS_PER_PAGE }
  
  const [clientsData, countData] = await Promise.all([
    api.getClients(params),
    api.getClientsCount(params)
  ])
  setClients(clientsData)
  setTotalClients(countData.total)
}

// Add pagination component after table
<Pagination
  currentPage={currentPage}
  totalPages={Math.ceil(totalClients / ITEMS_PER_PAGE)}
  totalItems={totalClients}
  itemsPerPage={ITEMS_PER_PAGE}
  onPageChange={setCurrentPage}
/>
```

### 4. Interviews.jsx (NEEDS UPDATE)
**Current**: Fetches all interviews at once
**Required Changes**:
```javascript
// Add state
const [currentPage, setCurrentPage] = useState(1)
const [totalInterviews, setTotalInterviews] = useState(0)
const ITEMS_PER_PAGE = 10

// Update fetchInterviews
const fetchInterviews = async () => {
  const params = { page: currentPage, limit: ITEMS_PER_PAGE }
  
  const [interviewsData, countData] = await Promise.all([
    api.getInterviews(params),
    api.getInterviewsCount(params)
  ])
  setInterviews(interviewsData)
  setTotalInterviews(countData.total)
}

// Add pagination component in sidebar
<Pagination
  currentPage={currentPage}
  totalPages={Math.ceil(totalInterviews / ITEMS_PER_PAGE)}
  totalItems={totalInterviews}
  itemsPerPage={ITEMS_PER_PAGE}
  onPageChange={setCurrentPage}
/>
```

### 5. Analytics.jsx (NO CHANGES NEEDED)
- Uses `limit: 1000` for filter dropdowns (acceptable)
- Not displaying paginated tables

### 6. Dashboard.jsx (NO CHANGES NEEDED)
- Fetches summary data only
- No large tables to paginate

### 7. Pipeline.jsx (NO CHANGES NEEDED)
- Uses Kanban board view
- Not a traditional table

## 🔧 Testing Checklist

### Backend Testing
- [ ] Test `/api/candidates?page=1&limit=10` returns 10 records
- [ ] Test `/api/candidates?page=2&limit=10` returns next 10 records
- [ ] Test `/api/candidates/count` returns correct total
- [ ] Test same for jobs, interviews, clients
- [ ] Test filters work with pagination

### Frontend Testing
- [ ] Resumes page shows 10 records per page
- [ ] Jobs page shows 10 records per page
- [ ] Clients page shows 10 records per page
- [ ] Interviews page shows 10 records per page
- [ ] Next/Previous buttons work correctly
- [ ] Page numbers display correctly
- [ ] "Showing X-Y of Z results" is accurate
- [ ] Pagination resets to page 1 when filters change
- [ ] Search works with pagination

## 📊 Performance Improvements

### Before Pagination
- **Candidates**: Loading 500+ records at once
- **Jobs**: Loading 100+ records at once
- **API Calls**: Multiple large payloads
- **Page Load**: Slow with large datasets

### After Pagination
- **All Pages**: Loading only 10 records at a time
- **API Calls**: Smaller, faster responses
- **Page Load**: Fast even with 1000+ total records
- **Network**: Reduced bandwidth usage

## 🚀 Next Steps

1. **Update Jobs.jsx** - Add pagination (see template above)
2. **Update Clients.jsx** - Add pagination (see template above)
3. **Update Interviews.jsx** - Add pagination (see template above)
4. **Test All Pages** - Verify pagination works correctly
5. **Monitor Performance** - Check API response times

## 📝 Example Implementation (Jobs.jsx)

```javascript
import { useState, useEffect } from 'react'
import { Pagination } from '@/components/ui/pagination'
import { api } from '@/lib/api'

export default function Jobs() {
  const [jobs, setJobs] = useState([])
  const [currentPage, setCurrentPage] = useState(1)
  const [totalJobs, setTotalJobs] = useState(0)
  const [loading, setLoading] = useState(true)
  const ITEMS_PER_PAGE = 10

  const fetchJobs = async () => {
    try {
      setLoading(true)
      const params = {
        page: currentPage,
        limit: ITEMS_PER_PAGE
      }
      
      const [jobsData, countData] = await Promise.all([
        api.getJobs(params),
        api.getJobsCount(params)
      ])
      
      setJobs(jobsData)
      setTotalJobs(countData.total)
    } catch (error) {
      console.error('Failed to fetch jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchJobs()
  }, [currentPage])

  return (
    <div className="space-y-6">
      <h1>Jobs</h1>
      
      {/* Job Cards Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {jobs.map(job => (
          <JobCard key={job.id} job={job} />
        ))}
      </div>
      
      {/* Pagination */}
      <Pagination
        currentPage={currentPage}
        totalPages={Math.ceil(totalJobs / ITEMS_PER_PAGE)}
        totalItems={totalJobs}
        itemsPerPage={ITEMS_PER_PAGE}
        onPageChange={setCurrentPage}
      />
    </div>
  )
}
```

## ✅ Summary

- **Backend**: ✅ All endpoints updated with `page` and `limit` parameters
- **API Client**: ✅ Count methods added for all resources
- **Pagination Component**: ✅ Already exists and ready to use
- **Resumes Page**: ✅ Already implemented
- **Jobs Page**: ⏳ Needs implementation
- **Clients Page**: ⏳ Needs implementation
- **Interviews Page**: ⏳ Needs implementation

**Default**: 10 records per page across all tables
**Performance**: Significantly improved with smaller API responses
**UX**: Better navigation with Previous/Next buttons and page numbers
