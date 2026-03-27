export async function DELETE(_req: Request, { params }: { params: { sessionId: string } }) {
  const apiUrl = process.env.API_URL || 'http://api:8080'
  const res = await fetch(`${apiUrl}/sessions/${params.sessionId}`, { method: 'DELETE' })
  const data = await res.json()
  return Response.json(data, { status: res.status })
}

export async function GET(_req: Request, { params }: { params: { sessionId: string } }) {
  const apiUrl = process.env.API_URL || 'http://api:8080'
  const res = await fetch(`${apiUrl}/sessions/${params.sessionId}/messages`)
  const data = await res.json()
  return Response.json(data, { status: res.status })
}

export async function PATCH(req: Request, { params }: { params: { sessionId: string } }) {
  const apiUrl = process.env.API_URL || 'http://api:8080'
  const body = await req.json()
  const res = await fetch(`${apiUrl}/sessions/${params.sessionId}/title`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  return Response.json(data, { status: res.status })
}
