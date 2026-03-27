export const dynamic = 'force-dynamic'

export async function GET() {
  const apiUrl = process.env.API_URL || 'http://api:8080'
  try {
    const res = await fetch(`${apiUrl}/sessions`, { cache: 'no-store' })
    const data = await res.json()
    return Response.json(data, { status: res.status })
  } catch {
    return Response.json({ sessions: [] }, { status: 503 })
  }
}
