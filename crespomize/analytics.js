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
  
  const platformEmoji = selectedPlatform === 'instagram' ? '📷' : '🎵';
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
    const platformEmoji = selectedPlatform === 'instagram' ? '📷' : '🎵';
    select.innerHTML = '<option value="">-- select an account --</option>' +
      '<option value="MOONMEDIA_TOTAL" class="moonmedia-option">🌙 All MoonMedia Analytics</option>' +
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
    
    const platformIcon = selectedPlatform === 'instagram' ? '📷' : '🎵';
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
  
  if (value >= 1000000000) {
    const val = value / 1000000000;
    const rangeRatio = range / value;
    if (rangeRatio < 0.01) return val.toFixed(3) + 'B';
    if (rangeRatio < 0.1) return val.toFixed(2) + 'B';
    return val.toFixed(1) + 'B';
  }
  if (value >= 1000000) {
    const val = value / 1000000;
    const rangeRatio = range / value;
    if (rangeRatio < 0.01) return val.toFixed(3) + 'M';
    if (rangeRatio < 0.1) return val.toFixed(2) + 'M';
    return val.toFixed(1) + 'M';
  }
  if (value >= 1000) {
    const val = value / 1000;
    const rangeRatio = range / value;
    if (rangeRatio < 0.01) return val.toFixed(2) + 'K';
    return val.toFixed(1) + 'K';
  }
  return value.toLocaleString();
}

function toggleLogScale(chartId) {
  const chart = chartInstances[chartId];
  if (!chart) return;

  const currentType = chart.options.scales.y.type;
  const newType = currentType === 'logarithmic' ? 'linear' : 'logarithmic';
  
  chart.options.scales.y.type = newType;
  
  if (chart.options.scales.y1) {
    chart.options.scales.y1.type = newType;
  }
  
  if (chartId === 'correlation' && chart.options.scales.x) {
    chart.options.scales.x.type = newType;
  }
  
  chart.update();

  const badge = document.querySelector(`[data-chart-id="${chartId}"]`);
  if (badge) {
    if (newType === 'logarithmic') {
      badge.classList.remove('inactive');
      badge.textContent = 'LOG SCALE';
    } else {
      badge.classList.add('inactive');
      badge.textContent = 'LINEAR';
    }
  }
}

function toggleTrendline(chartId) {
  const chart = chartInstances[chartId];
  if (!chart) return;

  trendlineStates[chartId] = !trendlineStates[chartId];
  const showTrendline = trendlineStates[chartId];

  const trendlineDataset = chart.data.datasets.find(ds => ds.label === 'Trend');
  if (trendlineDataset) {
    trendlineDataset.hidden = !showTrendline;
  }

  if (chart.options.scales.y1) {
    chart.options.scales.y1.display = showTrendline;
  }

  chart.update();

  const badge = document.querySelector(`[data-trendline-id="${chartId}"]`);
  if (badge) {
    if (showTrendline) {
      badge.classList.remove('inactive');
      badge.textContent = '📈 TREND ON';
    } else {
      badge.classList.add('inactive');
      badge.textContent = '📈 TREND OFF';
    }
  }

  const controls = document.querySelector(`[data-smoothness-controls="${chartId}"]`);
  if (controls) {
    controls.style.display = showTrendline ? 'inline-block' : 'none';
  }
}

function adjustTrendlineSmoothness(chartId, direction) {
  const chart = chartInstances[chartId];
  if (!chart) return;

  if (trendlineDaysAverage[chartId] === undefined) {
    trendlineDaysAverage[chartId] = 7;
  }

  trendlineDaysAverage[chartId] += direction;
  trendlineDaysAverage[chartId] = Math.max(1, trendlineDaysAverage[chartId]);

  const dataDataset = chart.data.datasets.find(ds => ds.label !== 'Trend');
  if (!dataDataset) return;

  const trendlineData = calculateMovingAverageByDays(dataDataset.data, trendlineDaysAverage[chartId]);

  const trendlineDataset = chart.data.datasets.find(ds => ds.label === 'Trend');
  if (trendlineDataset) {
    trendlineDataset.data = trendlineData;
  }

  chart.update();

  const display = document.querySelector(`[data-days-display="${chartId}"]`);
  if (display) {
    display.textContent = trendlineDaysAverage[chartId];
  }

  console.log(`Trendline for ${chartId}: ${trendlineDaysAverage[chartId]} days average`);
}

function createLineChart(container, title, historyData, datasets, useLog, chartId) {
  const chartDiv = document.createElement('div');
  chartDiv.className = 'chart-container';
  
  const canvas = document.createElement('canvas');
  canvas.id = chartId;
  
  const header = document.createElement('h3');
  header.textContent = title;
  
  const scaleBadge = document.createElement('span');
  scaleBadge.className = 'scale-badge' + (useLog ? '' : ' inactive');
  scaleBadge.textContent = useLog ? 'LOG SCALE' : 'LINEAR';
  scaleBadge.setAttribute('data-chart-id', chartId);
  scaleBadge.onclick = () => toggleLogScale(chartId);
  
  header.appendChild(scaleBadge);
  
  const exportBtn = document.createElement('button');
  exportBtn.className = 'export-btn';
  exportBtn.textContent = '💾 Export';
  exportBtn.onclick = () => exportChart(chartId, title);
  
  chartDiv.appendChild(header);
  chartDiv.appendChild(exportBtn);
  chartDiv.appendChild(canvas);
  container.appendChild(chartDiv);

  const ctx = canvas.getContext('2d');
  
  const allValues = datasets.flatMap(ds => ds.data.map(d => d.y)).filter(v => v > 0);
  const dataRange = {
    min: Math.min(...allValues),
    max: Math.max(...allValues)
  };

  chartInstances[chartId] = new Chart(ctx, {
    type: 'line',
    data: { datasets },
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
          display: true,
          labels: {
            color: '#0f0',
            font: { family: 'monospace', size: 12 }
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#0f0',
          bodyColor: '#0f0',
          borderColor: '#0f0',
          borderWidth: 1,
          callbacks: {
            label: function(context) {
              return context.dataset.label + ': ' + formatNumber(context.parsed.y);
            }
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'day',
            displayFormats: { day: 'MMM d, yyyy' }
          },
          ticks: { color: '#0f0', font: { family: 'monospace' } },
          grid: { color: 'rgba(0, 255, 0, 0.1)' }
        },
        y: {
          type: useLog ? 'logarithmic' : 'linear',
          ticks: {
            color: '#0f0',
            font: { family: 'monospace' },
            callback: function(value) {
              return formatNumberAxisSmart(value, dataRange);
            }
          },
          grid: { color: 'rgba(0, 255, 0, 0.1)' }
        }
      }
    }
  });
}

function createTimeBasedChart(container, title, videos, datasets, useLog, chartId, includeTrendline = false) {
  const chartDiv = document.createElement('div');
  chartDiv.className = 'chart-container';
  
  const canvas = document.createElement('canvas');
  canvas.id = chartId;
  
  const header = document.createElement('h3');
  header.textContent = title;
  
  const scaleBadge = document.createElement('span');
  scaleBadge.className = 'scale-badge' + (useLog ? '' : ' inactive');
  scaleBadge.textContent = useLog ? 'LOG SCALE' : 'LINEAR';
  scaleBadge.setAttribute('data-chart-id', chartId);
  scaleBadge.onclick = () => toggleLogScale(chartId);
  
  header.appendChild(scaleBadge);

  if (includeTrendline) {
    const trendlineBadge = document.createElement('span');
    trendlineBadge.className = 'trendline-badge inactive';
    trendlineBadge.textContent = '📈 TREND OFF';
    trendlineBadge.setAttribute('data-trendline-id', chartId);
    trendlineBadge.onclick = () => toggleTrendline(chartId);
    header.appendChild(trendlineBadge);

    trendlineStates[chartId] = false;
    trendlineDaysAverage[chartId] = 7;

    const smoothnessControls = document.createElement('span');
    smoothnessControls.className = 'smoothness-controls';
    smoothnessControls.setAttribute('data-smoothness-controls', chartId);
    smoothnessControls.style.display = 'none';

    const downBtn = document.createElement('button');
    downBtn.className = 'smoothness-btn';
    downBtn.textContent = '◄';
    downBtn.onclick = () => adjustTrendlineSmoothness(chartId, -1);

    const daysDisplay = document.createElement('span');
    daysDisplay.className = 'smoothness-btn';
    daysDisplay.textContent = '7';
    daysDisplay.style.cursor = 'default';
    daysDisplay.setAttribute('data-days-display', chartId);

    const upBtn = document.createElement('button');
    upBtn.className = 'smoothness-btn';
    upBtn.textContent = '►';
    upBtn.onclick = () => adjustTrendlineSmoothness(chartId, 1);

    smoothnessControls.appendChild(downBtn);
    smoothnessControls.appendChild(daysDisplay);
    smoothnessControls.appendChild(upBtn);
    
    header.appendChild(smoothnessControls);
  }
  
  const exportBtn = document.createElement('button');
  exportBtn.className = 'export-btn';
  exportBtn.textContent = '💾 Export';
  exportBtn.onclick = () => exportChart(chartId, title);
  
  chartDiv.appendChild(header);
  chartDiv.appendChild(exportBtn);
  chartDiv.appendChild(canvas);
  container.appendChild(chartDiv);

  const ctx = canvas.getContext('2d');

  if (includeTrendline && datasets.length > 0) {
    const trendlineData = calculateMovingAverageByDays(datasets[0].data, 7);
    
    datasets.push({
      label: 'Trend',
      data: trendlineData,
      type: 'line',
      borderColor: '#ffff00',
      backgroundColor: 'transparent',
      borderWidth: 3,
      pointRadius: 0,
      tension: 0.4,
      yAxisID: 'y1',
      hidden: true,
      order: 0
    });
  }
  
  const allValues = datasets.filter(ds => ds.label !== 'Trend').flatMap(ds => ds.data.map(d => d.y)).filter(v => v > 0);
  const dataRange = {
    min: Math.min(...allValues),
    max: Math.max(...allValues)
  };

  const trendlineValues = includeTrendline 
    ? datasets.find(ds => ds.label === 'Trend').data.map(d => d.y).filter(v => v > 0)
    : [];
  const trendlineRange = trendlineValues.length > 0 
    ? { min: Math.min(...trendlineValues), max: Math.max(...trendlineValues) }
    : dataRange;

  const scales = {
    x: {
      type: 'time',
      time: {
        unit: 'day',
        displayFormats: { day: 'MMM d, yyyy' }
      },
      ticks: { color: '#0f0', font: { family: 'monospace' } },
      grid: { color: 'rgba(0, 255, 0, 0.1)' }
    },
    y: {
      type: useLog ? 'logarithmic' : 'linear',
      position: 'left',
      ticks: {
        color: '#0f0',
        font: { family: 'monospace' },
        callback: function(value) {
          return formatNumberAxisSmart(value, dataRange);
        }
      },
      grid: { color: 'rgba(0, 255, 0, 0.1)' }
    }
  };

  if (includeTrendline) {
    scales.y1 = {
      type: useLog ? 'logarithmic' : 'linear',
      position: 'right',
      display: false,
      ticks: {
        color: '#ffff00',
        font: { family: 'monospace' },
        callback: function(value) {
          return formatNumberAxisSmart(value, trendlineRange);
        }
      },
      grid: {
        drawOnChartArea: false
      }
    };
  }

  chartInstances[chartId] = new Chart(ctx, {
    type: datasets[0].type || 'scatter',
    data: { datasets },
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
          display: true,
          labels: {
            color: '#0f0',
            font: { family: 'monospace', size: 12 },
            filter: function(item, chart) {
              if (item.text === 'Trend') {
                return trendlineStates[chartId] === true;
              }
              return true;
            }
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#0f0',
          bodyColor: '#0f0',
          borderColor: '#0f0',
          borderWidth: 1,
          callbacks: {
            label: function(context) {
              return context.dataset.label + ': ' + formatNumber(context.parsed.y);
            }
          }
        }
      },
      scales: scales
    }
  });
}

function renderDashboard() {
  chartInstances = {};
  trendlineStates = {};
  trendlineDaysAverage = {};

  const statsContainer = document.getElementById('statsSummary');
  
  const contentType = selectedPlatform === 'instagram' ? 'REELS' : 'POSTS';
  
  let statsHTML = `
    <div class="stat-card">
      <h4>👥 FOLLOWERS</h4>
      <div class="value">${formatNumber(accountData.followers)}</div>
    </div>
    <div class="stat-card">
      <h4>❤️ TOTAL LIKES</h4>
      <div class="value">${formatNumber(accountData.totalLikes)}</div>
    </div>
    <div class="stat-card">
      <h4>🎬 ${contentType} TRACKED</h4>
      <div class="value">${accountData.postsScraped}</div>
    </div>
    <div class="stat-card">
      <h4>📈 AVG ENGAGEMENT</h4>
      <div class="value">${accountData.videos.length > 0 ? (accountData.videos.reduce((sum, v) => sum + v.engagement, 0) / accountData.videos.length).toFixed(2) : 0}%</div>
    </div>
  `;

  if (isMoonMediaTotal) {
    statsHTML += `
      <div class="stat-card">
        <h4>👁️ TOTAL VIEWS</h4>
        <div class="value">${formatNumber(accountData.totalViews)}</div>
      </div>
      <div class="stat-card">
        <h4>⚡ VIEWS PER SECOND</h4>
        <div class="value">${accountData.viewsPerSecond.toFixed(2)}</div>
      </div>
      <div class="stat-card">
        <h4>🏢 TOTAL ACCOUNTS</h4>
        <div class="value">${accountData.accountCount}</div>
      </div>
    `;
  }

  statsContainer.innerHTML = statsHTML;

  const chartsContainer = document.getElementById('chartsList');
  chartsContainer.innerHTML = '';

  if (accountData.followersHistory && accountData.followersHistory.length > 0) {
    const followerValues = accountData.followersHistory.map(h => h.value);
    const useLogFollowers = shouldUseLogScale(followerValues);
    
    createLineChart(chartsContainer, '👥 Followers Per Scrape', 
      accountData.followersHistory,
      [{
        label: 'Followers',
        data: accountData.followersHistory.map(h => ({ x: h.date, y: h.value })),
        borderColor: '#9b59b6',
        backgroundColor: 'rgba(155, 89, 182, 0.1)',
        borderWidth: 3,
        tension: 0.4,
        fill: true
      }],
      useLogFollowers,
      'followers-history'
    );
  }

  if (accountData.totalLikesHistory && accountData.totalLikesHistory.length > 0) {
    const likesHistoryValues = accountData.totalLikesHistory.map(h => h.value);
    const useLogLikesHistory = shouldUseLogScale(likesHistoryValues);
    
    createLineChart(chartsContainer, '❤️ Total Likes Per Scrape',
      accountData.totalLikesHistory,
      [{
        label: 'Total Likes',
        data: accountData.totalLikesHistory.map(h => ({ x: h.date, y: h.value })),
        borderColor: '#e91e63',
        backgroundColor: 'rgba(233, 30, 99, 0.1)',
        borderWidth: 3,
        tension: 0.4,
        fill: true
      }],
      useLogLikesHistory,
      'likes-history'
    );
  }

  if (accountData.videos.length > 0) {
    const viewsData = accountData.videos.map(v => v.views);
    const likesData = accountData.videos.map(v => v.likes);
    const useLogViews = shouldUseLogScale(viewsData);
    const useLogLikes = shouldUseLogScale(likesData);

    createTimeBasedChart(chartsContainer, '👁️ Views Over Time',
      accountData.videos,
      [{
        label: 'Views',
        data: accountData.videos.map(v => ({ x: v.date, y: v.views })),
        borderColor: '#00d2d3',
        backgroundColor: 'rgba(0, 210, 211, 0.7)',
        pointRadius: 4,
        pointHoverRadius: 6
      }],
      useLogViews,
      'views-time',
      true
    );

    createTimeBasedChart(chartsContainer, '❤️ Likes Over Time',
      accountData.videos,
      [{
        label: 'Likes',
        data: accountData.videos.map(v => ({ x: v.date, y: v.likes })),
        borderColor: '#ff6b6b',
        backgroundColor: 'rgba(255, 107, 107, 0.7)',
        pointRadius: 4,
        pointHoverRadius: 6
      }],
      useLogLikes,
      'likes-time',
      true
    );

    createTimeBasedChart(chartsContainer, '📈 Engagement Rate Over Time',
      accountData.videos,
      [{
        label: 'Engagement %',
        data: accountData.videos.map(v => ({ x: v.date, y: v.engagement })),
        borderColor: '#2ecc71',
        backgroundColor: 'rgba(46, 204, 113, 0.7)',
        pointRadius: 4,
        pointHoverRadius: 6
      }],
      false,
      'engagement-time',
      true
    );

    const commentsData = accountData.videos.map(v => v.comments);
    const useLogComments = shouldUseLogScale(commentsData);
    
    createTimeBasedChart(chartsContainer, '💬 Comments Over Time',
      accountData.videos,
      [{
        label: 'Comments',
        data: accountData.videos.map(v => ({ x: v.date, y: v.comments })),
        borderColor: '#1abc9c',
        backgroundColor: 'rgba(26, 188, 156, 0.7)',
        pointRadius: 4,
        pointHoverRadius: 6
      }],
      useLogComments,
      'comments-time',
      true
    );

    if (selectedPlatform === 'tiktok') {
      const sharesData = accountData.videos.map(v => v.shares);
      const useLogShares = shouldUseLogScale(sharesData);
      
      createTimeBasedChart(chartsContainer, '🔄 Shares Over Time',
        accountData.videos,
        [{
          label: 'Shares',
          data: accountData.videos.map(v => ({ x: v.date, y: v.shares })),
          borderColor: '#e74c3c',
          backgroundColor: 'rgba(231, 76, 60, 0.7)',
          pointRadius: 4,
          pointHoverRadius: 6
        }],
        useLogShares,
        'shares-time',
        true
      );
    }

    // Likes vs Views Correlation Chart
    const correlationValues = accountData.videos.map(v => v.views);
    const useLogCorrelation = shouldUseLogScale(correlationValues);

    const chartDiv = document.createElement('div');
    chartDiv.className = 'chart-container';
    
    const canvas = document.createElement('canvas');
    canvas.id = 'correlation';
    
    const header = document.createElement('h3');
    header.textContent = '❤️ Likes vs Views Correlation';
    
    const scaleBadge = document.createElement('span');
    scaleBadge.className = 'scale-badge' + (useLogCorrelation ? '' : ' inactive');
    scaleBadge.textContent = useLogCorrelation ? 'LOG SCALE' : 'LINEAR';
    scaleBadge.setAttribute('data-chart-id', 'correlation');
    scaleBadge.onclick = () => toggleLogScale('correlation');
    
    header.appendChild(scaleBadge);
    
    const exportBtn = document.createElement('button');
    exportBtn.className = 'export-btn';
    exportBtn.textContent = '💾 Export';
    exportBtn.onclick = () => exportChart('correlation', 'Likes vs Views Correlation');
    
    chartDiv.appendChild(header);
    chartDiv.appendChild(exportBtn);
    chartDiv.appendChild(canvas);
    chartsContainer.appendChild(chartDiv);

    const ctx = canvas.getContext('2d');
    
    const allViews = accountData.videos.map(v => v.views).filter(v => v > 0);
    const allLikes = accountData.videos.map(v => v.likes).filter(v => v > 0);
    const dataRangeX = {
      min: Math.min(...allViews),
      max: Math.max(...allViews)
    };
    const dataRangeY = {
      min: Math.min(...allLikes),
      max: Math.max(...allLikes)
    };

    chartInstances['correlation'] = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: [{
          label: 'Posts',
          data: accountData.videos.map(v => ({ x: v.views, y: v.likes })),
          backgroundColor: 'rgba(0, 210, 211, 0.6)',
          borderColor: '#00d2d3',
          pointRadius: 6,
          pointHoverRadius: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 2.5,
        plugins: {
          legend: {
            display: true,
            labels: {
              color: '#0f0',
              font: { family: 'monospace', size: 12 }
            }
          },
          tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            titleColor: '#0f0',
            bodyColor: '#0f0',
            borderColor: '#0f0',
            borderWidth: 1,
            callbacks: {
              label: function(context) {
                return 'Views: ' + formatNumber(context.parsed.x) + ', Likes: ' + formatNumber(context.parsed.y);
              }
            }
          }
        },
        scales: {
          x: {
            type: useLogCorrelation ? 'logarithmic' : 'linear',
            title: {
              display: true,
              text: 'Views',
              color: '#0f0',
              font: { family: 'monospace', size: 14 }
            },
            ticks: {
              color: '#0f0',
              font: { family: 'monospace' },
              callback: function(value) {
                return formatNumberAxisSmart(value, dataRangeX);
              }
            },
            grid: { color: 'rgba(0, 255, 0, 0.1)' }
          },
          y: {
            type: useLogCorrelation ? 'logarithmic' : 'linear',
            title: {
              display: true,
              text: 'Likes',
              color: '#0f0',
              font: { family: 'monospace', size: 14 }
            },
            ticks: {
              color: '#0f0',
              font: { family: 'monospace' },
              callback: function(value) {
                return formatNumberAxisSmart(value, dataRangeY);
              }
            },
            grid: { color: 'rgba(0, 255, 0, 0.1)' }
          }
        }
      }
    });
  }
}

// Initialize when DOM is ready
window.addEventListener('load', () => {
  // Do nothing on load, wait for platform selection
});
