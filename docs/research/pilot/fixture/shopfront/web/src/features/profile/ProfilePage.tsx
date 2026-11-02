import { formatTime } from '../../utils/format'

interface User {
  name: string
  createdAt: string
  lastLoginAt: number
}

export function ProfilePage({ user }: { user: User }) {
  const joined = new Date(user.createdAt)
  return (
    <section className="profile">
      <h2>{user.name}</h2>
      <p>注册时间：{`${joined.getFullYear()}-${joined.getMonth() + 1}-${joined.getDate()}`}</p>
      <p>最近登录：{formatTime(user.lastLoginAt)}</p>
    </section>
  )
}
