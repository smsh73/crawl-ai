'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  FileText,
  Rss,
  Tag,
  Calendar,
  FileBarChart,
  Settings,
  Bot
} from 'lucide-react'

const navigation = [
  { name: '대시보드', href: '/', icon: LayoutDashboard },
  { name: '콘텐츠', href: '/contents', icon: FileText },
  { name: '소스', href: '/sources', icon: Rss },
  { name: '키워드', href: '/keywords', icon: Tag },
  { name: '스케줄', href: '/schedules', icon: Calendar },
  { name: '리포트', href: '/reports', icon: FileBarChart },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl flex items-center justify-center">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-gray-900">Crawl AI</h1>
            <p className="text-xs text-gray-500">Intelligence Platform</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href))

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <item.icon className={`w-5 h-5 ${isActive ? 'text-primary-600' : ''}`} />
              <span className="font-medium">{item.name}</span>
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-4 py-3 text-gray-600 hover:bg-gray-50 hover:text-gray-900 rounded-lg transition-colors"
        >
          <Settings className="w-5 h-5" />
          <span className="font-medium">설정</span>
        </Link>
      </div>
    </aside>
  )
}
