// Generate actionable insights from chart data

export const generateTimeToHireInsight = (data) => {
  if (!data || data.length < 2) return null
  
  const latest = data[data.length - 1]
  const previous = data[data.length - 2]
  const avg = data.reduce((sum, d) => sum + d.avg_days, 0) / data.length
  const change = ((latest.avg_days - previous.avg_days) / previous.avg_days * 100).toFixed(1)
  
  if (latest.avg_days > avg * 1.1) {
    return `Hiring velocity slowed by ${Math.abs(change)}% - consider streamlining interview process`
  } else if (latest.avg_days < avg * 0.9) {
    return `Hiring velocity improved by ${Math.abs(change)}% compared to previous month`
  }
  return `Average time to hire is ${latest.avg_days.toFixed(1)} days, ${latest.avg_days > 30 ? 'above' : 'within'} industry standard`
}

export const generateScoreDistributionInsight = (data) => {
  if (!data || data.length === 0) return null
  
  const total = data.reduce((sum, d) => sum + d.count, 0)
  if (total === 0) return null
  
  const highScorers = data.filter(d => d.range === '81-100')[0]?.count || 0
  const lowScorers = data.filter(d => ['0-20', '21-40'].includes(d.range)).reduce((sum, d) => sum + d.count, 0)
  const highPercent = ((highScorers / total) * 100).toFixed(0)
  
  if (highPercent >= 70) {
    return `${highPercent}% of candidates score above 80, indicating strong resume quality`
  } else if (highPercent >= 40) {
    return `${highPercent}% of candidates are high performers - good talent pool quality`
  } else if (lowScorers > total * 0.4) {
    return `${((lowScorers / total) * 100).toFixed(0)}% of resumes score below 40 - review sourcing channels`
  }
  return `Resume quality is balanced across score ranges`
}

export const generateDepartmentInsight = (data) => {
  if (!data || data.length === 0) return null
  
  const totalHired = data.reduce((sum, d) => sum + d.hired, 0)
  const totalOpen = data.reduce((sum, d) => sum + d.open, 0)
  
  if (totalHired === 0 && totalOpen === 0) return null
  
  const maxHired = Math.max(...data.map(d => d.hired))
  const minHired = Math.min(...data.map(d => d.hired))
  const topDept = data.find(d => d.hired === maxHired)
  const lowDept = data.filter(d => d.hired === minHired && d.open > 0)[0]
  
  if (maxHired > minHired * 3 && lowDept) {
    return `${lowDept.department} has low candidate inflow compared to other teams`
  } else if (topDept && topDept.hired > 0) {
    return `${topDept.department} leads hiring with ${topDept.hired} positions filled`
  } else if (totalOpen > totalHired * 2) {
    return `${totalOpen} open positions - accelerate recruitment efforts`
  }
  return `Hiring is balanced across departments`
}

export const generateSkillInsight = (data) => {
  if (!data || data.length === 0) return null
  
  const topSkill = data[0]
  const avgCount = data.reduce((sum, d) => sum + d.count, 0) / data.length
  
  if (topSkill.count > avgCount * 2) {
    return `${topSkill.skill} is the most in-demand skill with ${topSkill.count} candidates`
  } else if (topSkill.avg_score >= 85) {
    return `Candidates with ${topSkill.skill} show strong performance (avg ${topSkill.avg_score})`
  }
  return `Top skills: ${data.slice(0, 3).map(d => d.skill).join(', ')}`
}

export const generateResumeTrendInsight = (data) => {
  if (!data || data.length < 2) return null
  
  const latest = data[data.length - 1]
  const previous = data[data.length - 2]
  const change = latest.avg_score - previous.avg_score
  const trend = data.slice(-3).every((d, i, arr) => i === 0 || d.avg_score >= arr[i-1].avg_score)
  
  if (trend && change > 0) {
    return `Resume quality trending upward - ${change.toFixed(1)} point improvement this month`
  } else if (change < -3) {
    return `Resume scores dropped ${Math.abs(change).toFixed(1)} points - review screening criteria`
  } else if (latest.avg_score >= 80) {
    return `Strong candidate quality maintained at ${latest.avg_score.toFixed(1)} average score`
  }
  return `Average resume score is ${latest.avg_score.toFixed(1)} - consistent quality`
}

export const generateInterviewTrendInsight = (data) => {
  if (!data || data.length === 0) return null
  
  const latest = data[data.length - 1]
  const avgTech = data.reduce((sum, d) => sum + d.technical, 0) / data.length
  const avgComm = data.reduce((sum, d) => sum + d.communication, 0) / data.length
  
  if (latest.technical > avgTech + 5) {
    return `Technical interview scores improved - candidates well-prepared`
  } else if (latest.communication < avgComm - 5) {
    return `Communication scores declining - consider soft skills training resources`
  } else if (Math.abs(latest.technical - latest.communication) > 15) {
    return `${latest.technical > latest.communication ? 'Technical' : 'Communication'} skills significantly stronger than ${latest.technical > latest.communication ? 'communication' : 'technical'}`
  }
  return `Interview performance balanced across technical and communication skills`
}

export const generateFunnelInsight = (data) => {
  if (!data || data.length < 3) return null
  
  const total = data.find(d => d.stage === 'Total Candidates')?.count || 0
  const shortlisted = data.find(d => d.stage === 'Shortlisted')?.count || 0
  const selected = data.find(d => d.stage === 'Selected')?.count || 0
  
  if (total === 0) return null
  
  const conversionRate = ((selected / total) * 100).toFixed(1)
  const shortlistRate = ((shortlisted / total) * 100).toFixed(1)
  
  if (conversionRate >= 10) {
    return `Strong ${conversionRate}% conversion rate from application to hire`
  } else if (conversionRate < 3) {
    return `Low ${conversionRate}% conversion rate - review selection criteria or sourcing quality`
  } else if (shortlistRate < 15) {
    return `Only ${shortlistRate}% of candidates shortlisted - screening may be too strict`
  }
  return `${conversionRate}% of candidates successfully hired from total applicants`
}
