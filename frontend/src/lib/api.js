import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export const createClaim = (payload) => api.post('/claims', payload).then(r => r.data)

export const uploadEvidence = (claimId, images, video) => {
  const formData = new FormData()
  images.forEach((file) => formData.append('images', file))
  if (video) formData.append('video', video)
  return api.post(`/claims/${claimId}/evidence`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const verifyClaim = (claimId, pastClaimCount = 0, rejectedClaimCount = 0) =>
  api.post(`/claims/${claimId}/verify`, null, {
    params: { past_claim_count: pastClaimCount, rejected_claim_count: rejectedClaimCount },
    timeout: 5 * 60 * 1000, // 5 min ceiling — generous even for full LLM mode on slow hardware, but guarantees the UI eventually surfaces an error instead of hanging forever
  }).then(r => r.data)

export const getClaim = (claimId) => api.get(`/claims/${claimId}`).then(r => r.data)

export const getNetworkClaim = (claimId, otherClaimId) =>
  api.get(`/claims/${claimId}/network/${otherClaimId}`).then(r => r.data)

export const listClaims = () => api.get('/claims').then(r => r.data)

export const exportCsv = () => api.post('/export/csv').then(r => r.data)

export const downloadCsvUrl = '/api/export/csv'

export const healthCheck = () => api.get('/health').then(r => r.data)

export default api
