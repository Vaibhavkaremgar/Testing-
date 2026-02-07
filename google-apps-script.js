function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    
    if (data.action === 'updateSheet') {
      return updateSheet(data.data, data.sheetId);
    }
    
    return ContentService
      .createTextOutput(JSON.stringify({success: false, error: 'Unknown action'}))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({success: false, error: error.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function updateSheet(sheetData, sheetId) {
  try {
    // Open the specific spreadsheet by ID
    const spreadsheet = SpreadsheetApp.openById('1cfBQgzf8ROOOsXdB6KX66-1g1ZGoyHkFI-4DG3CgV_c');
    const sheet = spreadsheet.getActiveSheet();
    
    // Clear existing data
    sheet.clear();
    
    // Add the new data with resume text
    if (sheetData && sheetData.length > 0) {
      const range = sheet.getRange(1, 1, sheetData.length, sheetData[0].length);
      range.setValues(sheetData);
      
      // Format header row
      const headerRange = sheet.getRange(1, 1, 1, sheetData[0].length);
      headerRange.setFontWeight('bold');
      headerRange.setBackground('#4285f4');
      headerRange.setFontColor('white');
      
      // Auto-resize columns except resume text column
      for (let i = 1; i <= sheetData[0].length; i++) {
        if (i === 9) { // Resume text column (9th column)
          sheet.setColumnWidth(i, 300); // Set fixed width for resume text
        } else {
          sheet.autoResizeColumn(i);
        }
      }
    }
    
    return ContentService
      .createTextOutput(JSON.stringify({
        success: true, 
        message: `Updated ${sheetData.length - 1} candidates with resume text`,
        rowsUpdated: sheetData.length - 1
      }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({success: false, error: error.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({message: 'Candidate sync service is running'}))
    .setMimeType(ContentService.MimeType.JSON);
}