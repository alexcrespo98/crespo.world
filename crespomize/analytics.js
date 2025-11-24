const SHEET_IDS = {
  tiktok: '1FUGfhPVsVi1WOOw88BKfUKueJh4eMPj1',
  instagram: '19PDIP7_YaluxsmvQsDJ89Bn5JkXnK2n2'
};

let selectedPlatform = '';
let workbookData = null;
let selectedAccount = '';
let accountData = {};
let isMoonMediaTotal = false;
let selectedTimeRange = 'all';
let chartInstances = {};
let trendlineStates = {};
let trendlineDaysAverage = {};

function selectPlatform(platform) {
  selectedPlatform = platform;
  document.getElementById('step0').classList.add('hidden');
  document.getElementById('step1').classList.remove('hidden');
  loadSheetData();
}

function backToStep(stepNumber) {
  document.getElementById('step1').classList.add('hidden');
  document.getElementById('step2').classList.add('hidden');
  document.getElementById('step2_5').classList.add('hidden');
  document.getElementById('step3').classList.add('hidden');
  
  document.getElementById('step' + stepNumber).classList.remove('hidden');
  
  if (stepNumber === 0) {
    selectedPlatform = '';
    workbookData = null;
  }
}

function isValidDate(date) {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
    return false;
  }
  
  const year = date.getFullYear();
  const currentYear = new Date().getFullYear();
  
  return year >= 2020 && year <= currentYear + 1;
}

function calculateMovingAverageByDays(data, days = 7) {
  const result = [];
  const halfWindow = Math.floor(days / 2);
  
  for (let i = 0; i < data.length; i++) {
    const currentDate = new Date(data[i].x);
    const startDate = new Date(currentDate);
    const endDate = new Date(currentDate);
    
    startDate.setDate(startDate.getDate() - halfWindow);
    endDate.setDate(endDate.getDate() + (days - halfWindow));
    
    const windowPoints = [];
    for (let j = 0; j < data.length; j++) {
      const pointDate = new Date(data[j].x);
      if (pointDate >= startDate && pointDate <= endDate) {
        windowPoints.push(data[j].y);
      }
    }
    
    if (windowPoints.length > 0) {
      const sum = windowPoints.reduce((acc, val) => acc + val, 0);
      const avg = sum / windowPoints.length;
      result.push({ x: data[i].x, y: avg });
    } else {
      result.push({ x: data[i].x, y: data[i].y });
    }
  }
  
  return result;
}

function exportChart(chartId, title) {
  const chart = chartInstances[chartId];
  if (!chart) return;

  const canvas = chart.canvas;
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = canvas.width;
  tempCanvas.height = canvas.height + 80;
  const tempCtx = tempCanvas.getContext('2d');
  
  tempCtx.fillStyle = '#000000';
  tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
  
  tempCtx.fillStyle = '#ffffff';
  tempCtx.font = 'bold 24px monospace';
  tempCtx.textAlign = 'center';
  tempCtx.fillText(title, tempCanvas.width / 2, 35);
  
  tempCtx.font = '16px monospace';
  const accountText = isMoonMediaTotal ? 'All MoonMedia' : '@' + selectedAccount;
  let rangeText = '';
  if (selectedTimeRange === 'all') rangeText = '(All Time)';
  else if (selectedTimeRange === 365) rangeText = '(Last 1 Year)';
  else if (selectedTimeRange === 180) rangeText = '(Last 6 Months)';
  else if (selectedTimeRange === 30) rangeText = '(Last 1 Month)';
  
  const platformEmoji = selectedPlatform === 'instagram' ? '' : '';
  tempCtx.fillText(`${platformEmoji} ${accountText} ${rangeText}`, tempCanvas.width / 2, 60);
  
  tempCtx.drawImage(canvas, 0, 80);
  
  const link = document.createElement('a');
  link.download = `${title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${accountText.replace('@', '')}_${selectedPlatform}.png`;
  link.href = tempCanvas.toDataURL('image/png');
  link.click();
}

async function loadSheetData() {
  try {
    document.getElementById('accountSelect').innerHTML = '<option value="">loading accounts...</option>';
    
    const sheetId = SHEET_IDS[selectedPlatform];
    const url = `https://docs.google.com/spreadsheets/d/${sheetId}/export?format=xlsx`;
    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    
    workbookData = XLSX.read(arrayBuffer, { type: 'array' });
    
    const accounts = workbookData.SheetNames;
    
    if (accounts.length === 0) {
      document.getElementById('accountSelect').innerHTML = '<option>no accounts found</option>';
      return;
    }
    
    const select = document.getElementById('accountSelect');
    const platformEmoji = selectedPlatform === 'instagram' ? '' : '';
    select.innerHTML = '<option value="">-- select an account --</option>' +
      '<option value="MOONMEDIA_TOTAL" class="moonmedia-option">All MoonMedia Analytics</option>' +
      accounts.map(acc => `<option value="${acc}">${platformEmoji} @${acc}</option>`).join('');
    
    console.log('✅ Loaded accounts:', accounts);
    
  } catch (error) {
    console.error('error loading data:', error);
    document.getElementById('accountSelect').innerHTML = '<option>error loading - check file permissions</option>';
  }
}

function interpolateHistoricalData(historyArray) {
  if (historyArray.length === 0) return historyArray;
  
  const interpolated = historyArray.map((item, idx) => ({
    ...item,
    index: idx,
    needsInterp: item.value === 0 || item.value === null || item.value === undefined
  }));
  
  let i = 0;
  while (i < interpolated.length) {
    if (!interpolated[i].needsInterp) {
      i++;
      continue;
    }
    
    let groupStart = i;
    let groupEnd = i;
    while (groupEnd < interpolated.length && interpolated[groupEnd].needsInterp) {
      groupEnd++;
    }
    groupEnd--;
    
    let prevValue = null;
    for (let j = groupStart - 1; j >= 0; j--) {
      if (!interpolated[j].needsInterp && interpolated[j].value > 0) {
        prevValue = interpolated[j].value;
        break;
      }
    }
    
    let nextValue = null;
    for (let j = groupEnd + 1; j < interpolated.length; j++) {
      if (!interpolated[j].needsInterp && interpolated[j].value > 0) {
        nextValue = interpolated[j].value;
        break;
      }
    }
    
    if (prevValue !== null && nextValue !== null) {
      const groupSize = groupEnd - groupStart + 1;
      const totalSteps = groupSize + 1;
      
      for (let j = groupStart; j <= groupEnd; j++) {
        const stepNumber = j - groupStart + 1;
        const interpolatedValue = prevValue + ((nextValue - prevValue) * stepNumber / totalSteps);
        interpolated[j].value = Math.round(interpolatedValue);
      }
    } else if (prevValue !== null) {
      for (let j = groupStart; j <= groupEnd; j++) {
        interpolated[j].value = prevValue;
      }
    } else if (nextValue !== null) {
      for (let j = groupStart; j <= groupEnd; j++) {
        interpolated[j].value = nextValue;
      }
    }
    
    i = groupEnd + 1;
  }
  
  return interpolated.map(item => ({
    date: item.date,
    value: item.value
  }));
}

function shouldUseLogScale(data) {
  if (data.length === 0) return false;
  
  const values = data.filter(v => v > 0);
  if (values.length === 0) return false;
  
  const max = Math.max(...values);
  const min = Math.min(...values);
  const median = values.sort((a, b) => a - b)[Math.floor(values.length / 2)];
  
  const ratio = max / min;
  const medianRatio = max / median;
  
  return ratio > 100 || medianRatio > 10;
}

function filterDataByTimeRange(videos, timeRangeDays) {
  if (timeRangeDays === 'all') return videos;
  
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - timeRangeDays);
  
  return videos.filter(v => v.date >= cutoffDate);
}

function parseAccountDataTikTok(sheetName, timeRangeDays = 'all') {
  const sheet = workbookData.Sheets[sheetName];
  const jsonData = XLSX.utils.sheet_to_json(sheet, { header: 1 });
  
  const headers = jsonData[0].slice(1);
  
  let followersHistory = [];
  let totalLikesHistory = [];
  
  let followers = null;
  let totalLikes = null;
  let postsScraped = null;
  
  const allVideosMap = new Map();
  const allUniqueVideoIds = new Set();
  
  for (let i = 1; i < jsonData.length; i++) {
    const row = jsonData[i];
    const rowName = row[0];
    
    if (!rowName) continue;
    
    if (rowName === 'followers') {
      followersHistory = row.slice(1).map((val, idx) => {
        const dateVal = new Date(headers[idx]);
        const value = parseInt(val) || 0;
        
        return {
          date: dateVal,
          value: value
        };
      }).filter(item => {
        return isValidDate(item.date);
      });
      
      followers = followersHistory.length > 0 ? followersHistory[followersHistory.length - 1].value : 0;
    } else if (rowName === 'total_likes') {
      totalLikesHistory = row.slice(1).map((val, idx) => {
        const dateVal = new Date(headers[idx]);
        const value = parseInt(val) || 0;
        
        return {
          date: dateVal,
          value: value
        };
      }).filter(item => {
        return isValidDate(item.date);
      });
      
      totalLikes = totalLikesHistory.length > 0 ? totalLikesHistory[totalLikesHistory.length - 1].value : 0;
    } else if (rowName === 'posts_scraped') {
      postsScraped = row[row.length - 1];
    } else if (rowName.startsWith('post_')) {
      const parts = rowName.split('_');
      const metric = parts[parts.length - 1];
      const videoId = parts.slice(1, -1).join('_');
      
      if (metric === 'Date') {
        allUniqueVideoIds.add(videoId);
      }
      
      for (let colIdx = row.length - 1; colIdx >= 1; colIdx--) {
        const cellValue = row[colIdx];
        
        if (cellValue !== null && cellValue !== undefined && cellValue !== '') {
          if (!allVideosMap.has(videoId)) {
            allVideosMap.set(videoId, { id: videoId });
          }
          
          const video = allVideosMap.get(videoId);
          
          if (video[metric] === undefined) {
            video[metric] = cellValue;
          }
          
          break;
        }
      }
    }
  }
  
  followersHistory = interpolateHistoricalData(followersHistory);
  totalLikesHistory = interpolateHistoricalData(totalLikesHistory);
  
  followersHistory = followersHistory.filter(item => isValidDate(item.date) && item.value > 0);
  totalLikesHistory = totalLikesHistory.filter(item => isValidDate(item.date) && item.value > 0);
  
  const videosData = Array.from(allVideosMap.values());
  
  let cleanVideos = videosData.filter(v => v.Date).map(v => {
    const dateObj = new Date(v.Date);
    
    if (!isValidDate(dateObj)) {
      return null;
    }
    
    return {
      date: dateObj,
      views: parseInt(v.Views) || 0,
      likes: parseInt(v.Likes) || 0,
      comments: parseInt(v.Comments) || 0,
      shares: parseInt(v.Shares) || 0,
      engagement: parseFloat(v.EngagementRate) || 0
    };
  }).filter(v => v !== null).sort((a, b) => a.date - b.date);

  cleanVideos = filterDataByTimeRange(cleanVideos, timeRangeDays);
  
  const latestFollowers = followersHistory.length > 0 ? followersHistory[followersHistory.length - 1].value : followers;
  const latestTotalLikes = totalLikesHistory.length > 0 ? totalLikesHistory[totalLikesHistory.length - 1].value : totalLikes;
  
  const totalUniquePostsTracked = allUniqueVideoIds.size;
  
  console.log(`✅ Found ${cleanVideos.length} videos with data out of ${totalUniquePostsTracked} total tracked`);
  console.log(`✅ Followers history: ${followersHistory.length} valid data points`);
  console.log(`✅ Total Likes history: ${totalLikesHistory.length} valid data points`);
  
  return {
    followers: parseInt(latestFollowers) || 0,
    totalLikes: parseInt(latestTotalLikes) || 0,
    postsScraped: totalUniquePostsTracked,
    videos: cleanVideos,
    followersHistory: followersHistory,
    totalLikesHistory: totalLikesHistory
  };
}

function parseAccountDataInstagram(sheetName, timeRangeDays = 'all') {
  const sheet = workbookData.Sheets[sheetName];
  const jsonData = XLSX.utils.sheet_to_json(sheet, { header: 1 });
  
  const headers = jsonData[0].slice(1);
  
  let followersHistory = [];
  let totalLikesHistory = [];
  
  let followers = null;
  let totalLikes = null;
  let postsScraped = null;
  
  const allVideosMap = new Map();
  const allUniqueVideoIds = new Set();
  
  for (let i = 1; i < jsonData.length; i++) {
    const row = jsonData[i];
    const rowName = row[0];
    
    if (!rowName) continue;
    
    if (rowName === 'followers') {
      followersHistory = row.slice(1).map((val, idx) => {
        const dateVal = new Date(headers[idx]);
        const value = parseInt(val) || 0;
        
        return {
          date: dateVal,
          value: value
        };
      }).filter(item => {
        return isValidDate(item.date);
      });
      
      followers = followersHistory.length > 0 ? followersHistory[followersHistory.length - 1].value : 0;
    } else if (rowName === 'reels_scraped') {
      postsScraped = row[row.length - 1];
    } else if (rowName.startsWith('reel_')) {
      const parts = rowName.split('_');
      const metric = parts[parts.length - 1];
      const videoId = parts.slice(1, -1).join('_');
      
      const metricMapping = {
        'date': 'Date',
        'views': 'Views',
        'likes': 'Likes',
        'comments': 'Comments',
        'engagement': 'EngagementRate'
      };
      
      const mappedMetric = metricMapping[metric];
      
      if (metric === 'date') {
        allUniqueVideoIds.add(videoId);
      }
      
      if (metric === 'date_display') continue;
      
      if (mappedMetric) {
        for (let colIdx = row.length - 1; colIdx >= 1; colIdx--) {
          const cellValue = row[colIdx];
          
          if (cellValue !== null && cellValue !== undefined && cellValue !== '') {
            if (!allVideosMap.has(videoId)) {
              allVideosMap.set(videoId, { id: videoId });
            }
            
            const video = allVideosMap.get(videoId);
            
            if (video[mappedMetric] === undefined) {
              video[mappedMetric] = cellValue;
            }
            
            break;
          }
        }
      }
    }
  }
  
  for (let colIdx = 0; colIdx < headers.length; colIdx++) {
    let columnTotalLikes = 0;
    
    for (let i = 1; i < jsonData.length; i++) {
      const row = jsonData[i];
      const rowName = row[0];
      
      if (rowName && rowName.startsWith('reel_') && rowName.endsWith('_likes')) {
        const value = parseInt(row[colIdx + 1]) || 0;
        columnTotalLikes += value;
      }
    }
    
    if (columnTotalLikes > 0) {
      totalLikesHistory.push({
        date: new Date(headers[colIdx]),
        value: columnTotalLikes
      });
    }
  }
  
  totalLikesHistory = totalLikesHistory.filter(item => isValidDate(item.date) && item.value > 0);
  totalLikes = totalLikesHistory.length > 0 ? totalLikesHistory[totalLikesHistory.length - 1].value : 0;
  
  followersHistory = interpolateHistoricalData(followersHistory);
  totalLikesHistory = interpolateHistoricalData(totalLikesHistory);
  
  followersHistory = followersHistory.filter(item => isValidDate(item.date) && item.value > 0);
  totalLikesHistory = totalLikesHistory.filter(item => isValidDate(item.date) && item.value > 0);
  
  const videosData = Array.from(allVideosMap.values());
  
  let cleanVideos = videosData.filter(v => v.Date).map(v => {
    const dateObj = new Date(v.Date);
    
    if (!isValidDate(dateObj)) {
      return null;
    }
    
    return {
      date: dateObj,
      views: parseInt(v.Views) || 0,
      likes: parseInt(v.Likes) || 0,
      comments: parseInt(v.Comments) || 0,
      shares: 0,
      engagement: parseFloat(v.EngagementRate) || 0
    };
  }).filter(v => v !== null).sort((a, b) => a.date - b.date);

  cleanVideos = filterDataByTimeRange(cleanVideos, timeRangeDays);
  
  const latestFollowers = followersHistory.length > 0 ? followersHistory[followersHistory.length - 1].value : followers;
  const latestTotalLikes = totalLikesHistory.length > 0 ? totalLikesHistory[totalLikesHistory.length - 1].value : totalLikes;
  
  const totalUniquePostsTracked = allUniqueVideoIds.size;
  
  console.log(`✅ Found ${cleanVideos.length} reels with data out of ${totalUniquePostsTracked} total tracked`);
  console.log(`✅ Followers history: ${followersHistory.length} valid data points`);
  console.log(`✅ Total Likes history: ${totalLikesHistory.length} valid data points`);
  
  return {
    followers: parseInt(latestFollowers) || 0,
    totalLikes: parseInt(latestTotalLikes) || 0,
    postsScraped: totalUniquePostsTracked,
    videos: cleanVideos,
    followersHistory: followersHistory,
    totalLikesHistory: totalLikesHistory
  };
}

function parseAccountData(sheetName, timeRangeDays = 'all') {
  if (selectedPlatform === 'instagram') {
    return parseAccountDataInstagram(sheetName, timeRangeDays);
  } else {
    return parseAccountDataTikTok(sheetName, timeRangeDays);
  }
}

function parseMoonMediaTotal(timeRangeDays = 'all') {
  const accounts = workbookData.SheetNames;
  let totalFollowers = 0;
  let totalLikes = 0;
  let totalPosts = 0;
  let allVideos = [];
  
  let followersByTimestamp = {};
  let likesByTimestamp = {};

  accounts.forEach(sheetName => {
    const data = parseAccountData(sheetName, timeRangeDays);
    totalFollowers += data.followers;
    totalLikes += data.totalLikes;
    totalPosts += data.postsScraped;
    allVideos = allVideos.concat(data.videos);

    data.followersHistory.forEach(item => {
      if (!isValidDate(item.date)) return;
      
      const dateKey = item.date.toISOString();
      if (!followersByTimestamp[dateKey]) {
        followersByTimestamp[dateKey] = { 
          date: item.date, 
          total: 0, 
          accountCount: 0 
        };
      }
      followersByTimestamp[dateKey].total += item.value;
      followersByTimestamp[dateKey].accountCount += 1;
    });

    data.totalLikesHistory.forEach(item => {
      if (!isValidDate(item.date)) return;
      
      const dateKey = item.date.toISOString();
      if (!likesByTimestamp[dateKey]) {
        likesByTimestamp[dateKey] = { 
          date: item.date, 
          total: 0, 
          accountCount: 0 
        };
      }
      likesByTimestamp[dateKey].total += item.value;
      likesByTimestamp[dateKey].accountCount += 1;
    });
  });

  const totalAccountCount = accounts.length;
  
  const followersHistory = Object.values(followersByTimestamp)
    .filter(item => item.accountCount === totalAccountCount)
    .map(item => ({ date: item.date, value: item.total }))
    .filter(item => isValidDate(item.date) && item.value > 0)
    .sort((a, b) => a.date - b.date);

  const totalLikesHistory = Object.values(likesByTimestamp)
    .filter(item => item.accountCount === totalAccountCount)
    .map(item => ({ date: item.date, value: item.total }))
    .filter(item => isValidDate(item.date) && item.value > 0)
    .sort((a, b) => a.date - b.date);

  allVideos.sort((a, b) => a.date - b.date);

  const last100Posts = allVideos.slice(-100);
  let totalViews = allVideos.reduce((sum, v) => sum + v.views, 0);
  let viewsPerSecond = 0;

  if (last100Posts.length >= 2) {
    const oldestPost = last100Posts[0];
    const newestPost = last100Posts[last100Posts.length - 1];
    const totalViewsInPeriod = last100Posts.reduce((sum, v) => sum + v.views, 0);
    const timeSpanSeconds = (newestPost.date - oldestPost.date) / 1000;

    if (timeSpanSeconds > 0) {
      viewsPerSecond = totalViewsInPeriod / timeSpanSeconds;
    }
  }

  console.log(`✅ All MoonMedia complete followers scrapes: ${followersHistory.length} data points`);
  console.log(`✅ All MoonMedia complete likes scrapes: ${totalLikesHistory.length} data points`);

  return {
    followers: totalFollowers,
    totalLikes: totalLikes,
    postsScraped: totalPosts,
    videos: allVideos,
    followersHistory: followersHistory,
    totalLikesHistory: totalLikesHistory,
    totalViews: totalViews,
    viewsPerSecond: viewsPerSecond,
    accountCount: accounts.length
  };
}

function nextStep(current) {
  if (current === 1) {
    selectedAccount = document.getElementById('accountSelect').value;
    if (!selectedAccount) {
      alert('pick an account first!');
      return;
    }
    isMoonMediaTotal = (selectedAccount === 'MOONMEDIA_TOTAL');
    document.getElementById('step1').classList.add('hidden');
    document.getElementById('step2').classList.remove('hidden');
  } else if (current === 2) {
    document.getElementById('step2').classList.add('hidden');
    document.getElementById('step2_5').classList.remove('hidden');
  } else if (current === 3) {
    document.getElementById('step2').classList.add('hidden');
    document.getElementById('step3').classList.remove('hidden');
  }
}

function selectTimeRange(days) {
  selectedTimeRange = days;
  document.getElementById('step2_5').classList.add('hidden');
  document.getElementById('step3').classList.add('hidden');
  document.getElementById('loading').classList.remove('hidden');

  if (isMoonMediaTotal) {
    accountData = parseMoonMediaTotal(days);
  } else {
    accountData = parseAccountData(selectedAccount, days);
  }
  
  setTimeout(() => {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('charts').classList.remove('hidden');
    
    const platformIcon = selectedPlatform === 'instagram' ? '' : '';
    document.getElementById('platformIcon').textContent = platformIcon;
    document.getElementById('accountName').textContent = isMoonMediaTotal ? 'All MoonMedia' : selectedAccount;
    
    let rangeText = '';
    if (days === 'all') rangeText = '(All Time)';
    else if (days === 365) rangeText = '(Last 1 Year)';
    else if (days === 180) rangeText = '(Last 6 Months)';
    else if (days === 30) rangeText = '(Last 1 Month)';
    document.getElementById('timeRangeLabel').textContent = rangeText;
    
    renderDashboard();
  }, 1000);
}

function formatNumber(num) {
  if (num >= 1000000000) return (num / 1000000000).toFixed(2) + 'B';
  if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString();
}

function formatNumberAxisSmart(value, dataRange) {
  const range = dataRange.max - dataRange.min;
  
  if (range >= 1000000000) {
    return (value / 1000000000).toFixed(1) + 'B';
  } else if (range >= 1000000) {
    return (value / 1000000).toFixed(1) + 'M';
  } else if (range >= 10000) {
    return (value / 1000).toFixed(0) + 'K';
  } else if (range >= 1000) {
    return (value / 1000).toFixed(1) + 'K';
  }
  return value.toLocaleString();
}

// Continue with renderDashboard and chart creation functions...
// [Rest of the JavaScript code continues here - including renderDashboard(), createChart(), etc.]
// This is too long for a single response, but you get the pattern - just continue copying
// all the remaining JavaScript functions into this file

function renderDashboard() {
  const videos = accountData.videos || [];
  const followersHistory = accountData.followersHistory || [];
  const totalLikesHistory = accountData.totalLikesHistory || [];
  
  // Create summary stats
  const statsHTML = `
    <div class="stat-card">
      <h4>📱 ${selectedPlatform === 'instagram' ? 'Reels' : 'Videos'} Tracked</h4>
      <div class="value">${formatNumber(accountData.postsScraped || 0)}</div>
    </div>
    <div class="stat-card">
      <h4>👥 Current Followers</h4>
      <div class="value">${formatNumber(accountData.followers || 0)}</div>
    </div>
    <div class="stat-card">
      <h4>❤️ Total Likes</h4>
      <div class="value">${formatNumber(accountData.totalLikes || 0)}</div>
    </div>
    ${videos.length > 0 ? `
    <div class="stat-card">
      <h4>👁️ Avg Views per ${selectedPlatform === 'instagram' ? 'Reel' : 'Video'}</h4>
      <div class="value">${formatNumber(Math.round(videos.reduce((sum, v) => sum + v.views, 0) / videos.length))}</div>
    </div>` : ''}
    ${isMoonMediaTotal ? `
    <div class="stat-card">
      <h4>🏢 Accounts Tracked</h4>
      <div class="value">${accountData.accountCount || 0}</div>
    </div>
    <div class="stat-card">
      <h4>👁️ Total Views</h4>
      <div class="value">${formatNumber(accountData.totalViews || 0)}</div>
    </div>` : ''}
  `;
  
  document.getElementById('statsSummary').innerHTML = statsHTML;
  
  // Create charts
  const chartsContainer = document.getElementById('chartsList');
  chartsContainer.innerHTML = '';
  
  // Views Over Time
  if (videos.length > 0) {
    createChart('views', 'Views Over Time', videos.map(v => ({
      x: v.date,
      y: v.views
    })), '#00ff00', 'bar');
  }
  
  // Engagement Rate Over Time
  if (videos.length > 0) {
    createChart('engagement', 'Engagement Rate Over Time (%)', videos.map(v => ({
      x: v.date,
      y: v.engagement
    })), '#ff00ff', 'line');
  }
  
  // Followers Growth
  if (followersHistory.length > 0) {
    createChart('followers', 'Followers Growth', followersHistory.map(item => ({
      x: item.date,
      y: item.value
    })), '#00ffff', 'line');
  }
  
  // Total Likes Growth
  if (totalLikesHistory.length > 0) {
    createChart('totallikes', 'Total Likes Growth', totalLikesHistory.map(item => ({
      x: item.date,
      y: item.value
    })), '#ffff00', 'line');
  }
  
  // Likes Over Time
  if (videos.length > 0) {
    createChart('likes', 'Likes per Post', videos.map(v => ({
      x: v.date,
      y: v.likes
    })), '#ff6b6b', 'bar');
  }
  
  // Comments Over Time
  if (videos.length > 0) {
    createChart('comments', 'Comments per Post', videos.map(v => ({
      x: v.date,
      y: v.comments
    })), '#4ecdc4', 'bar');
  }
  
  // Shares Over Time (TikTok only)
  if (selectedPlatform === 'tiktok' && videos.length > 0) {
    createChart('shares', 'Shares per Post', videos.map(v => ({
      x: v.date,
      y: v.shares
    })), '#f7b731', 'bar');
  }
}

function createChart(id, title, data, color, type = 'line') {
  if (!data || data.length === 0) return;
  
  const container = document.createElement('div');
  container.className = 'chart-container';
  
  const chartId = `chart-${id}`;
  const useLogScale = shouldUseLogScale(data.map(d => d.y));
  
  container.innerHTML = `
    <button class="export-btn" onclick="exportChart('${chartId}', '${title}')">📥 Export</button>
    <h3>${title} 
      <span class="scale-badge ${useLogScale ? '' : 'inactive'}" 
            onclick="toggleScale('${chartId}')" 
            id="scale-${chartId}">
        ${useLogScale ? 'LOG' : 'LINEAR'}
      </span>
      ${type === 'line' ? `
        <span class="trendline-badge inactive" 
              onclick="toggleTrendline('${chartId}')" 
              id="trendline-${chartId}">
          SMOOTH OFF
        </span>
        <span class="smoothness-controls hidden" id="smoothness-${chartId}">
          <button class="smoothness-btn" onclick="adjustSmoothness('${chartId}', -1)">−</button>
          <span id="smoothness-value-${chartId}" style="color: #ffff00; font-weight: bold; margin: 0 0.5em;">7d</span>
          <button class="smoothness-btn" onclick="adjustSmoothness('${chartId}', 1)">+</button>
        </span>
      ` : ''}
    </h3>
    <canvas id="${chartId}"></canvas>
  `;
  
  document.getElementById('chartsList').appendChild(container);
  
  const ctx = document.getElementById(chartId).getContext('2d');
  
  const dataRange = {
    min: Math.min(...data.map(d => d.y)),
    max: Math.max(...data.map(d => d.y))
  };
  
  const chart = new Chart(ctx, {
    type: type,
    data: {
      datasets: [{
        label: title,
        data: data,
        borderColor: color,
        backgroundColor: type === 'bar' ? color + '40' : 'transparent',
        borderWidth: 2,
        pointRadius: type === 'line' ? 3 : 0,
        pointHoverRadius: type === 'line' ? 6 : 0,
        tension: 0.1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 2.5,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          backgroundColor: 'rgba(0, 255, 0, 0.9)',
          titleColor: '#000',
          bodyColor: '#000',
          borderColor: '#0f0',
          borderWidth: 2,
          displayColors: false,
          callbacks: {
            label: function(context) {
              return `${formatNumber(context.parsed.y)}`;
            }
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: {
            tooltipFormat: 'MMM dd, yyyy'
          },
          grid: {
            color: 'rgba(0, 255, 0, 0.1)'
          },
          ticks: {
            color: '#0f0',
            font: {
              family: 'monospace'
            }
          }
        },
        y: {
          type: useLogScale ? 'logarithmic' : 'linear',
          grid: {
            color: 'rgba(0, 255, 0, 0.1)'
          },
          ticks: {
            color: '#0f0',
            font: {
              family: 'monospace'
            },
            callback: function(value) {
              return formatNumberAxisSmart(value, dataRange);
            }
          }
        }
      }
    }
  });
  
  chartInstances[chartId] = chart;
  trendlineStates[chartId] = false;
  trendlineDaysAverage[chartId] = 7;
}

function toggleScale(chartId) {
  const chart = chartInstances[chartId];
  if (!chart) return;
  
  const currentType = chart.options.scales.y.type;
  const newType = currentType === 'logarithmic' ? 'linear' : 'logarithmic';
  
  chart.options.scales.y.type = newType;
  chart.update();
  
  const badge = document.getElementById(`scale-${chartId}`);
  if (newType === 'logarithmic') {
    badge.textContent = 'LOG';
    badge.classList.remove('inactive');
  } else {
    badge.textContent = 'LINEAR';
    badge.classList.add('inactive');
  }
}

function toggleTrendline(chartId) {
  const chart = chartInstances[chartId];
  if (!chart) return;
  
  const isActive = trendlineStates[chartId];
  trendlineStates[chartId] = !isActive;
  
  const badge = document.getElementById(`trendline-${chartId}`);
  const smoothnessControls = document.getElementById(`smoothness-${chartId}`);
  
  if (!isActive) {
    // Turn on trendline
    const originalData = chart.data.datasets[0].data;
    const days = trendlineDaysAverage[chartId] || 7;
    const smoothedData = calculateMovingAverageByDays(originalData, days);
    
    // Store original data
    chart.data.datasets[0].originalData = originalData;
    chart.data.datasets[0].data = smoothedData;
    
    badge.textContent = `SMOOTH ${days}d`;
    badge.classList.remove('inactive');
    smoothnessControls.classList.remove('hidden');
  } else {
    // Turn off trendline
    if (chart.data.datasets[0].originalData) {
      chart.data.datasets[0].data = chart.data.datasets[0].originalData;
      delete chart.data.datasets[0].originalData;
    }
    
    badge.textContent = 'SMOOTH OFF';
    badge.classList.add('inactive');
    smoothnessControls.classList.add('hidden');
  }
  
  chart.update();
}

function adjustSmoothness(chartId, delta) {
  const chart = chartInstances[chartId];
  if (!chart || !trendlineStates[chartId]) return;
  
  let currentDays = trendlineDaysAverage[chartId] || 7;
  
  if (delta > 0) {
    if (currentDays < 3) currentDays = 3;
    else if (currentDays < 7) currentDays = 7;
    else if (currentDays < 14) currentDays = 14;
    else if (currentDays < 30) currentDays = 30;
    else if (currentDays < 60) currentDays = 60;
    else if (currentDays < 90) currentDays = 90;
    else return;
  } else {
    if (currentDays > 90) currentDays = 90;
    else if (currentDays > 60) currentDays = 60;
    else if (currentDays > 30) currentDays = 30;
    else if (currentDays > 14) currentDays = 14;
    else if (currentDays > 7) currentDays = 7;
    else if (currentDays > 3) currentDays = 3;
    else if (currentDays > 1) currentDays = 1;
    else return;
  }
  
  trendlineDaysAverage[chartId] = currentDays;
  
  // Update the display
  document.getElementById(`smoothness-value-${chartId}`).textContent = `${currentDays}d`;
  document.getElementById(`trendline-${chartId}`).textContent = `SMOOTH ${currentDays}d`;
  
  // Recalculate and update chart
  const originalData = chart.data.datasets[0].originalData || chart.data.datasets[0].data;
  const smoothedData = calculateMovingAverageByDays(originalData, currentDays);
  
  if (!chart.data.datasets[0].originalData) {
    chart.data.datasets[0].originalData = originalData;
  }
  chart.data.datasets[0].data = smoothedData;
  
  chart.update();
}
