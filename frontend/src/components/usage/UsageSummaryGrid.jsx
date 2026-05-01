import UsageCard from './UsageCard'

const FEATURE_TITLES = {
  interview_credits: 'Interview Credits',
  resume_scans: 'Resume Parse',
  active_jobs: 'Active Jobs',
  user_seats: 'User Seats',
}

export default function UsageSummaryGrid({ summary = {} }) {
  const featureEntries = Object.entries(summary)

  if (featureEntries.length === 0) {
    return null
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {featureEntries.map(([featureName, metric]) => (
        <UsageCard
          key={featureName}
          title={FEATURE_TITLES[featureName] || featureName}
          total={metric.unlimited ? null : (metric.total ?? 0)}
          used={metric.used ?? 0}
          remaining={metric.unlimited ? null : (metric.remaining ?? 0)}
          unlimited={Boolean(metric.unlimited)}
        />
      ))}
    </div>
  )
}
