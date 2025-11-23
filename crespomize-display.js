// crespomize-display.js
// UI and chart functions for crespomize analytics

// This file depends on crespomize-data.js being loaded first.
// State is managed via the AppState namespace defined in crespomize-data.js.

function selectPlatform(platform) {
  AppState.selectedPlatform = platform;
  document.getElementById('step0').classList.add('hidden');
  document.getElementById('step1').classList.remove('hidden');
  loadSheetData();
}

function backToStep(stepNumber) {
  document.getElementById('step1').classList.add('hidden');
  document.getElementById('step2_5').classList.add('hidden');
  document.getElementById('step3').classList.add('hidden');
  
  document.getElementById('step' + stepNumber).classList.remove('hidden');
  
  if (stepNumber === 0) {
    AppState.selectedPlatform = '';
    AppState.workbookData = null;
  }
}

function selectTimeRange(days) {
  AppState.selectedTimeRange = days;
  document.getElementById('step2_5').classList.add('hidden');
  document.getElementById('step3').classList.add('hidden');
  document.getElementById('loading').classList.remove('hidden');

  if (AppState.isMoonMediaTotal) {
    AppState.accountData = parseMoonMediaTotal(days);
  } else {
    AppState.accountData = parseAccountData(AppState.selectedAccount, days);
  }
  
  setTimeout(() => {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('charts').classList.remove('hidden');
    
    document.getElementById('accountName').textContent = AppState.isMoonMediaTotal ? 'All MoonMedia' : AppState.selectedAccount;
    
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

function exportChart(chartId, title) {
  const chart = AppState.chartInstances[chartId];
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
  const accountText = AppState.isMoonMediaTotal ? 'All MoonMedia' : '@' + AppState.selectedAccount;
  let rangeText = '';
  if (AppState.selectedTimeRange === 'all') rangeText = '(All Time)';
  else if (AppState.selectedTimeRange === 365) rangeText = '(Last 1 Year)';
  else if (AppState.selectedTimeRange === 180) rangeText = '(Last 6 Months)';
  else if (AppState.selectedTimeRange === 30) rangeText = '(Last 1 Month)';
  
  tempCtx.fillText(`${accountText} ${rangeText}`, tempCanvas.width / 2, 60);
  
  tempCtx.drawImage(canvas, 0, 80);
  
  const link = document.createElement('a');
  link.download = `${title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${accountText.replace('@', '')}_${AppState.selectedPlatform}.png`;
  link.href = tempCanvas.toDataURL('image/png');
  link.click();
}

function toggleLogScale(chartId) {
  const chart = AppState.chartInstances[chartId];
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
  const chart = AppState.chartInstances[chartId];
  if (!chart) return;

  AppState.trendlineStates[chartId] = !AppState.trendlineStates[chartId];
  const showTrendline = AppState.trendlineStates[chartId];

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
      badge.textContent = 'TREND ON';
    } else {
      badge.classList.add('inactive');
      badge.textContent = 'TREND OFF';
    }
  }

  const controls = document.querySelector(`[data-smoothness-controls="${chartId}"]`);
  if (controls) {
    controls.style.display = showTrendline ? 'inline-block' : 'none';
  }
}

function adjustTrendlineSmoothness(chartId, direction) {
  const chart = AppState.chartInstances[chartId];
  if (!chart) return;

  if (AppState.trendlineDaysAverage[chartId] === undefined) {
    AppState.trendlineDaysAverage[chartId] = 7;
  }

  AppState.trendlineDaysAverage[chartId] += direction;
  AppState.trendlineDaysAverage[chartId] = Math.max(1, AppState.trendlineDaysAverage[chartId]);

  const dataDataset = chart.data.datasets.find(ds => ds.label !== 'Trend');
  if (!dataDataset) return;

  const trendlineData = calculateMovingAverageByDays(dataDataset.data, AppState.trendlineDaysAverage[chartId]);

  const trendlineDataset = chart.data.datasets.find(ds => ds.label === 'Trend');
  if (trendlineDataset) {
    trendlineDataset.data = trendlineData;
  }

  chart.update();

  const display = document.querySelector(`[data-days-display="${chartId}"]`);
  if (display) {
    display.textContent = AppState.trendlineDaysAverage[chartId];
  }

  console.log(`Trendline for ${chartId}: ${AppState.trendlineDaysAverage[chartId]} days average`);
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

  AppState.chartInstances[chartId] = new Chart(ctx, {
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
    trendlineBadge.textContent = 'TREND OFF';
    trendlineBadge.setAttribute('data-trendline-id', chartId);
    trendlineBadge.onclick = () => toggleTrendline(chartId);
    header.appendChild(trendlineBadge);

    AppState.trendlineStates[chartId] = false;
    AppState.trendlineDaysAverage[chartId] = 7;

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

  AppState.chartInstances[chartId] = new Chart(ctx, {
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
                return AppState.trendlineStates[chartId] === true;
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
  AppState.chartInstances = {};
  AppState.trendlineStates = {};
  AppState.trendlineDaysAverage = {};

  const statsContainer = document.getElementById('statsSummary');
  
  const contentType = AppState.selectedPlatform === 'instagram' ? 'REELS' : 'POSTS';
  
  let statsHTML = `
    <div class="stat-card">
      <h4>FOLLOWERS</h4>
      <div class="value">${formatNumber(AppState.accountData.followers)}</div>
    </div>
    <div class="stat-card">
      <h4>TOTAL LIKES</h4>
      <div class="value">${formatNumber(AppState.accountData.totalLikes)}</div>
    </div>
    <div class="stat-card">
      <h4>${contentType} TRACKED</h4>
      <div class="value">${AppState.accountData.postsScraped}</div>
    </div>
    <div class="stat-card">
      <h4>AVG ENGAGEMENT</h4>
      <div class="value">${AppState.accountData.videos.length > 0 ? (AppState.accountData.videos.reduce((sum, v) => sum + v.engagement, 0) / AppState.accountData.videos.length).toFixed(2) : 0}%</div>
    </div>
  `;

  if (AppState.isMoonMediaTotal) {
    statsHTML += `
      <div class="stat-card">
        <h4>TOTAL VIEWS</h4>
        <div class="value">${formatNumber(AppState.accountData.totalViews)}</div>
      </div>
      <div class="stat-card">
        <h4>VIEWS PER SECOND</h4>
        <div class="value">${AppState.accountData.viewsPerSecond.toFixed(2)}</div>
      </div>
      <div class="stat-card">
        <h4>TOTAL ACCOUNTS</h4>
        <div class="value">${AppState.accountData.accountCount}</div>
      </div>
    `;
  }

  statsContainer.innerHTML = statsHTML;

  const chartsContainer = document.getElementById('chartsList');
  chartsContainer.innerHTML = '';

  if (AppState.accountData.followersHistory && AppState.accountData.followersHistory.length > 0) {
    const followerValues = AppState.accountData.followersHistory.map(h => h.value);
    const useLogFollowers = shouldUseLogScale(followerValues);
    
    createLineChart(chartsContainer, 'Followers Per Scrape', 
      AppState.accountData.followersHistory,
      [{
        label: 'Followers',
        data: AppState.accountData.followersHistory.map(h => ({ x: h.date, y: h.value })),
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

  if (AppState.accountData.totalLikesHistory && AppState.accountData.totalLikesHistory.length > 0) {
    const likesHistoryValues = AppState.accountData.totalLikesHistory.map(h => h.value);
    const useLogLikesHistory = shouldUseLogScale(likesHistoryValues);
    
    createLineChart(chartsContainer, 'Total Likes Per Scrape',
      AppState.accountData.totalLikesHistory,
      [{
        label: 'Total Likes',
        data: AppState.accountData.totalLikesHistory.map(h => ({ x: h.date, y: h.value })),
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

  if (AppState.accountData.videos.length > 0) {
    const viewsData = AppState.accountData.videos.map(v => v.views);
    const likesData = AppState.accountData.videos.map(v => v.likes);
    const useLogViews = shouldUseLogScale(viewsData);
    const useLogLikes = shouldUseLogScale(likesData);

    createTimeBasedChart(chartsContainer, 'Views Over Time',
      AppState.accountData.videos,
      [{
        label: 'Views',
        data: AppState.accountData.videos.map(v => ({ x: v.date, y: v.views })),
        borderColor: '#00d2d3',
        backgroundColor: 'rgba(0, 210, 211, 0.7)',
        pointRadius: 4,
        pointHoverRadius: 6
      }],
      useLogViews,
      'views-time',
      true
    );

    createTimeBasedChart(chartsContainer, 'Likes Over Time',
      AppState.accountData.videos,
      [{
        label: 'Likes',
        data: AppState.accountData.videos.map(v => ({ x: v.date, y: v.likes })),
        borderColor: '#ff6b6b',
        backgroundColor: 'rgba(255, 107, 107, 0.7)',
        pointRadius: 4,
        pointHoverRadius: 6
      }],
      useLogLikes,
      'likes-time',
      true
    );

    createTimeBasedChart(chartsContainer, 'Engagement Rate Over Time',
      AppState.accountData.videos,
      [{
        label: 'Engagement %',
        data: AppState.accountData.videos.map(v => ({ x: v.date, y: v.engagement })),
        borderColor: '#2ecc71',
        backgroundColor: 'rgba(46, 204, 113, 0.7)',
        pointRadius: 4,
        pointHoverRadius: 6
      }],
      false,
      'engagement-time',
      true
    );

    const commentsData = AppState.accountData.videos.map(v => v.comments);
    const useLogComments = shouldUseLogScale(commentsData);
    
    createTimeBasedChart(chartsContainer, 'Comments Over Time',
      AppState.accountData.videos,
      [{
        label: 'Comments',
        data: AppState.accountData.videos.map(v => ({ x: v.date, y: v.comments })),
        borderColor: '#1abc9c',
        backgroundColor: 'rgba(26, 188, 156, 0.7)',
        pointRadius: 4,
        pointHoverRadius: 6
      }],
      useLogComments,
      'comments-time',
      true
    );

    if (AppState.selectedPlatform === 'tiktok') {
      const sharesData = AppState.accountData.videos.map(v => v.shares);
      const useLogShares = shouldUseLogScale(sharesData);
      
      createTimeBasedChart(chartsContainer, 'Shares Over Time',
        AppState.accountData.videos,
        [{
          label: 'Shares',
          data: AppState.accountData.videos.map(v => ({ x: v.date, y: v.shares })),
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

    const correlationValues = AppState.accountData.videos.map(v => v.views);
    const useLogCorrelation = shouldUseLogScale(correlationValues);

    const chartDiv = document.createElement('div');
    chartDiv.className = 'chart-container';
    
    const canvas = document.createElement('canvas');
    canvas.id = 'correlation';
    
    const header = document.createElement('h3');
    header.textContent = 'Likes vs Views Correlation';
    
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
    
    const allViews = AppState.accountData.videos.map(v => v.views).filter(v => v > 0);
    const allLikes = AppState.accountData.videos.map(v => v.likes).filter(v => v > 0);
    const dataRangeX = {
      min: Math.min(...allViews),
      max: Math.max(...allViews)
    };
    const dataRangeY = {
      min: Math.min(...allLikes),
      max: Math.max(...allLikes)
    };

    AppState.chartInstances['correlation'] = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: [{
          label: 'Posts',
          data: AppState.accountData.videos.map(v => ({ x: v.views, y: v.likes })),
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

window.addEventListener('load', () => {
  // Do nothing on load, wait for platform selection
});
