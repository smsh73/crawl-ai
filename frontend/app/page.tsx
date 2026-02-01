'use client'

import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  FileText,
  Rss,
  Bell,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle
} from 'lucide-react'
import { StatsCard } from '@/components/StatsCard'
import { RecentContents } from '@/components/RecentContents'
import { KeywordCloud } from '@/components/KeywordCloud'
import { api } from '@/lib/api'

export default function Dashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: () => api.getStats(7),
  })

  const { data: recentContents } = useQuery({
    queryKey: ['contents', 'recent'],
    queryFn: () => api.getContents({ page: 1, page_size: 10 }),
  })

  const totalContents = stats?.status_counts
    ? Object.values(stats.status_counts).reduce((a: number, b: number) => a + b, 0)
    : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">대시보드</h1>
          <p className="text-gray-500 mt-1">AI Intelligence Platform 현황</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Clock className="w-4 h-4" />
          마지막 업데이트: {new Date().toLocaleString('ko-KR')}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="수집된 콘텐츠"
          value={totalContents}
          icon={<FileText className="w-5 h-5" />}
          color="blue"
          trend={stats?.daily_counts?.length > 1 ? '+12%' : undefined}
        />
        <StatsCard
          title="활성 소스"
          value={stats?.status_counts?.processed || 0}
          icon={<Rss className="w-5 h-5" />}
          color="green"
        />
        <StatsCard
          title="처리 완료"
          value={stats?.status_counts?.processed || 0}
          icon={<CheckCircle className="w-5 h-5" />}
          color="emerald"
        />
        <StatsCard
          title="알림 발송"
          value={stats?.status_counts?.notified || 0}
          icon={<Bell className="w-5 h-5" />}
          color="purple"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Daily Activity Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">일별 수집 현황</h2>
            <span className="text-sm text-gray-500">최근 7일</span>
          </div>
          <DailyChart data={stats?.daily_counts || []} />
        </div>

        {/* Top Keywords */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">인기 키워드</h2>
          <KeywordCloud keywords={stats?.top_keywords || []} />
        </div>
      </div>

      {/* Recent Contents */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">최근 수집 콘텐츠</h2>
          <a href="/contents" className="text-sm text-primary-600 hover:text-primary-700">
            전체 보기 →
          </a>
        </div>
        <RecentContents contents={recentContents?.items || []} />
      </div>
    </div>
  )
}

// Simple bar chart component
function DailyChart({ data }: { data: { date: string; count: number }[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-gray-400">
        데이터가 없습니다
      </div>
    )
  }

  const maxCount = Math.max(...data.map(d => d.count))

  return (
    <div className="h-48 flex items-end gap-2">
      {data.map((item, index) => (
        <div key={index} className="flex-1 flex flex-col items-center gap-2">
          <div
            className="w-full bg-primary-500 rounded-t transition-all duration-300 hover:bg-primary-600"
            style={{
              height: `${(item.count / maxCount) * 100}%`,
              minHeight: item.count > 0 ? '8px' : '0'
            }}
          />
          <span className="text-xs text-gray-500">
            {new Date(item.date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
          </span>
        </div>
      ))}
    </div>
  )
}
