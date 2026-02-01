'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Filter, ExternalLink, Tag, Clock, Star } from 'lucide-react'
import { api, Content } from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'
import { ko } from 'date-fns/locale'

export default function ContentsPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [minImportance, setMinImportance] = useState<number | undefined>()

  const { data, isLoading } = useQuery({
    queryKey: ['contents', page, search, minImportance],
    queryFn: () => api.getContents({
      page,
      page_size: 20,
      min_importance: minImportance
    }),
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">콘텐츠</h1>
        <p className="text-gray-500 mt-1">수집된 AI 관련 콘텐츠 목록</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <div className="flex-1 min-w-[200px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="검색어 입력..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={minImportance || ''}
            onChange={(e) => setMinImportance(e.target.value ? Number(e.target.value) : undefined)}
            className="border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">모든 중요도</option>
            <option value="0.8">높음 (80%+)</option>
            <option value="0.6">중간 (60%+)</option>
            <option value="0.4">낮음 (40%+)</option>
          </select>
        </div>
      </div>

      {/* Content List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="text-center py-12 text-gray-500">로딩 중...</div>
        ) : data?.items?.length === 0 ? (
          <div className="text-center py-12 text-gray-500">콘텐츠가 없습니다</div>
        ) : (
          data?.items?.map((content: Content) => (
            <ContentCard key={content.id} content={content} />
          ))
        )}
      </div>

      {/* Pagination */}
      {data && data.total > 20 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 border border-gray-200 rounded-lg disabled:opacity-50"
          >
            이전
          </button>
          <span className="px-4 py-2">
            {page} / {Math.ceil(data.total / 20)}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(data.total / 20)}
            className="px-4 py-2 border border-gray-200 rounded-lg disabled:opacity-50"
          >
            다음
          </button>
        </div>
      )}
    </div>
  )
}

function ContentCard({ content }: { content: Content }) {
  const importanceColor = content.importance_score >= 0.8
    ? 'text-red-500'
    : content.importance_score >= 0.6
    ? 'text-yellow-500'
    : 'text-green-500'

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 card-hover animate-fadeIn">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <a
            href={content.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-lg font-medium text-gray-900 hover:text-primary-600 flex items-center gap-2"
          >
            {content.title}
            <ExternalLink className="w-4 h-4" />
          </a>

          {content.summary && (
            <p className="mt-2 text-gray-600 line-clamp-2">{content.summary}</p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-4 text-sm">
            {content.categories && content.categories.length > 0 && (
              <div className="flex items-center gap-1 text-gray-500">
                <Tag className="w-4 h-4" />
                {content.categories.slice(0, 3).join(', ')}
              </div>
            )}

            {content.collected_at && (
              <div className="flex items-center gap-1 text-gray-400">
                <Clock className="w-4 h-4" />
                {formatDistanceToNow(new Date(content.collected_at), {
                  addSuffix: true,
                  locale: ko
                })}
              </div>
            )}
          </div>

          {content.matched_keywords && content.matched_keywords.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {content.matched_keywords.map((keyword, i) => (
                <span
                  key={i}
                  className="px-2 py-1 bg-primary-50 text-primary-700 rounded-full text-xs"
                >
                  {keyword}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col items-center">
          <Star className={`w-5 h-5 ${importanceColor}`} />
          <span className={`text-sm font-medium ${importanceColor}`}>
            {Math.round((content.importance_score || 0) * 100)}%
          </span>
        </div>
      </div>
    </div>
  )
}
