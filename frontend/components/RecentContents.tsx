import { ExternalLink, Star } from 'lucide-react'
import { Content } from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'
import { ko } from 'date-fns/locale'

interface RecentContentsProps {
  contents: Content[]
}

export function RecentContents({ contents }: RecentContentsProps) {
  if (!contents || contents.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        최근 수집된 콘텐츠가 없습니다
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-100">
      {contents.map((content) => (
        <div
          key={content.id}
          className="py-4 flex items-start gap-4 hover:bg-gray-50 -mx-6 px-6 transition-colors"
        >
          <div className="flex-1 min-w-0">
            <a
              href={content.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-gray-900 hover:text-primary-600 flex items-center gap-2 line-clamp-1"
            >
              {content.title}
              <ExternalLink className="w-3 h-3 flex-shrink-0" />
            </a>
            {content.summary && (
              <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                {content.summary}
              </p>
            )}
            <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
              {content.categories && content.categories[0] && (
                <span className="px-2 py-0.5 bg-gray-100 rounded-full">
                  {content.categories[0]}
                </span>
              )}
              {content.collected_at && (
                <span>
                  {formatDistanceToNow(new Date(content.collected_at), {
                    addSuffix: true,
                    locale: ko
                  })}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1 text-sm">
            <Star className={`w-4 h-4 ${
              (content.importance_score || 0) >= 0.7
                ? 'text-yellow-500'
                : 'text-gray-300'
            }`} />
            <span className="text-gray-500">
              {Math.round((content.importance_score || 0) * 100)}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
