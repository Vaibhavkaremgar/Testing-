# User Resume Tab Implementation Guide

## Changes Needed in Resumes.jsx

### 1. Add role check at the top
```javascript
const isAdmin = currentUser?.role === 'admin'
```

### 2. Conditionally hide Upload Section (line ~520)
```javascript
{/* Upload Section - Admin Only */}
{isAdmin && (
  <Card>
    <CardHeader>
      <CardTitle className="text-base flex items-center gap-2">
        <Upload className="h-5 w-5" />
        Upload Resumes
      </CardTitle>
    </CardHeader>
    {/* ... rest of upload section ... */}
  </Card>
)}
```

### 3. Filter candidates for users (modify fetchCandidates function around line ~90)
```javascript
const fetchCandidates = useCallback(async () => {
  try {
    let data;
    if (isAdmin) {
      // Admin sees all candidates
      data = await api.getCandidates({ search, client: selectedClient })
    } else {
      // Users see only assigned candidates
      data = await api.getMyAssignedCandidates()
    }
    
    let filteredData = (data || []).filter(c => c.stage !== 'APPLIED')
    // ... rest of filtering logic ...
  }
}, [search, selectedClient, jobFilter, scoreFilter, statusFilter, isAdmin])
```

### 4. Hide Edit/Delete buttons for users (in table actions around line ~850)
```javascript
<td className="p-4" onClick={(e) => e.stopPropagation()}>
  <div className="flex items-center justify-end gap-2">
    <Button variant="ghost" size="icon" onClick={() => handleViewResume(candidate)}>
      <Eye className="h-4 w-4" />
    </Button>
    {isAdmin && (
      <>
        <Button variant="ghost" size="icon" onClick={() => handleEdit(candidate)}>
          <Edit className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => handleDelete(candidate.id)}>
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      </>
    )}
  </div>
</td>
```

### 5. Add Review buttons in modal for users (around line ~1050)
```javascript
{/* Action Buttons */}
<div className="pt-4 border-t">
  <div className="flex gap-3">
    {isAdmin ? (
      // Admin sees email buttons
      <>
        <Button className="flex-1" onClick={handleSendInterview}>
          Send Interview Invitation
        </Button>
        <Button variant="destructive" className="flex-1" onClick={handleReject}>
          Decline Invitation
        </Button>
      </>
    ) : (
      // Users see review buttons
      <>
        <Button 
          className="flex-1"
          onClick={async () => {
            try {
              await api.reviewCandidate(selectedCandidate.id, 'interview')
              alert('Interview invitation sent!')
              handleCloseModal()
              await fetchCandidates()
            } catch (error) {
              alert(`Failed: ${error.message}`)
            }
          }}
        >
          Send Interview
        </Button>
        <Button 
          variant="destructive"
          className="flex-1"
          onClick={async () => {
            try {
              await api.reviewCandidate(selectedCandidate.id, 'reject')
              alert('Candidate rejected')
              handleCloseModal()
              await fetchCandidates()
            } catch (error) {
              alert(`Failed: ${error.message}`)
            }
          }}
        >
          Reject
        </Button>
      </>
    )}
  </div>
</div>
```

### 6. Hide admin-only features
- Hide checkbox column for users
- Hide assignment bar for users
- Hide sync buttons for users
- Keep filters, search, and export for both

## Summary of Changes:
1. ✅ Upload section hidden for users
2. ✅ Users see only assigned candidates
3. ✅ Users can view candidate details modal
4. ✅ Users have Send Interview/Reject buttons in modal
5. ✅ Users cannot edit/delete candidates
6. ✅ Same table and modal structure for both roles

## Files to Modify:
- `frontend/src/pages/Resumes.jsx` - Add role-based conditionals

## API Methods Already Available:
- `api.getMyAssignedCandidates()` - Get assigned candidates
- `api.reviewCandidate(id, action)` - Review with 'interview' or 'reject'
