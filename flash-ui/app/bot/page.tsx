"use client"

import { useState, useEffect } from 'react'
import Link from 'next/link'
import Image from 'next/image'

interface BotInfo {
  username: string
  name: string
  password: string
}

export default function BotControl() {
  const [token, setToken] = useState('')
  const [status, setStatus] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [botStatus, setBotStatus] = useState<'online' | 'offline'>('offline')
  const [botInfo, setBotInfo] = useState<BotInfo | null>(null)
  const [restartStatus, setRestartStatus] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  useEffect(() => {
    const fetchBotStatus = async () => {
      try {
        const response = await fetch('/bot/status')
        const data = await response.json()
        setBotStatus(data.status)
      } catch (error) {
        console.error('Failed to fetch bot status:', error)
      }
    }

    const fetchBotInfo = async () => {
      try {
        const response = await fetch('/bot/get_info')
        const data = await response.json()
        setBotInfo(data)
      } catch (error) {
        console.error('Failed to fetch bot info:', error)
      }
    }

    fetchBotStatus()
    fetchBotInfo()
    const statusInterval = setInterval(fetchBotStatus, 5000)
    const infoInterval = setInterval(fetchBotInfo, 5000)
    return () => {
      clearInterval(statusInterval)
      clearInterval(infoInterval)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus(null)

    try {
      const response = await fetch('/bot/set_token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to update token')
      }

      setStatus({ message: data.status, type: 'success' })
      setToken('') // Clear the input after successful update
    } catch (error) {
      setStatus({
        message: error instanceof Error ? error.message : 'An unexpected error occurred',
        type: 'error'
      })
    }
  }

  const handleRestart = async () => {
    setRestartStatus(null)
    try {
      const response = await fetch('/bot/restart')
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to restart bot')
      }

      setRestartStatus({ message: data.success, type: 'success' })
    } catch (error) {
      setRestartStatus({
        message: error instanceof Error ? error.message : 'An unexpected error occurred',
        type: 'error'
      })
    }
  }

  const handleCopyPassword = async () => {
    if (!botInfo) return
    try {
      await navigator.clipboard.writeText(botInfo.password)
    } catch {
      // Handle copy failure silently
    }
  }

  return (
    <main className="min-h-screen p-8 overflow-auto">
      <div className="max-w-md mx-auto space-y-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Bot Control</h1>
          <Link
            href="/"
            className="btn-primary"
          >
            Back to Dashboard
          </Link>
        </div>

        <div className="card p-6">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-[var(--muted-foreground)]">Status:</span>
              <span className={`px-2 py-1 rounded text-sm ${
                botStatus === 'online'
                  ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100'
                  : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100'
              }`}>
                {botStatus}
              </span>
            </div>
            {botInfo && (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-[var(--muted-foreground)]">Username:</span>
                  <span className="text-sm">@{botInfo.username}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-[var(--muted-foreground)]">Name:</span>
                  <span className="text-sm">{botInfo.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-[var(--muted-foreground)]">OTP Code:</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{botInfo.password}</span>
                    <button
                      onClick={handleCopyPassword}
                      className="p-1 hover:bg-[var(--muted)] rounded transition-colors"
                      title="Copy to clipboard"
                    >
                      <Image
                        src="/copy-solid.svg"
                        alt="Copy"
                        width={16}
                        height={16}
                        className="text-[var(--muted-foreground)]"
                      />
                    </button>
                  </div>
                </div>
                <div className="pt-2">
                  <button
                    onClick={handleRestart}
                    className="w-full py-2 px-4 bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors"
                  >
                    Restart Bot
                  </button>
                  {restartStatus && (
                    <div className={`mt-2 p-2 rounded text-sm ${
                      restartStatus.type === 'success'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100'
                        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100'
                    }`}>
                      {restartStatus.message}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Update Bot Token</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="token" className="block text-sm font-medium mb-2">
                Bot Token
              </label>
              <input
                type="text"
                id="token"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter your bot token"
                className="w-full p-2 border rounded bg-[var(--card)] text-[var(--card-foreground)] border-[var(--border)]"
                required
              />
            </div>

            <button
              type="submit"
              className="btn-primary w-full"
            >
              Update Token
            </button>
          </form>

          {status && (
            <div className={`mt-4 p-3 rounded ${
              status.type === 'success'
                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100'
                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100'
            }`}>
              {status.message}
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
