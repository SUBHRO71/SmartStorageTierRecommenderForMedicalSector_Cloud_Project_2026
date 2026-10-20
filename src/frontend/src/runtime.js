const config = window.CLOUDTIER_CONFIG || {};
export const apiUrl = config.apiUrl || import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000/api';
export const userPoolId = config.userPoolId || import.meta.env.VITE_COGNITO_USER_POOL_ID;
export const clientId = config.clientId || import.meta.env.VITE_COGNITO_CLIENT_ID;
export const region = config.region || import.meta.env.VITE_AWS_REGION || 'us-east-1';
export const cloudMode = config.mode === 'AWS' || Boolean(userPoolId);
