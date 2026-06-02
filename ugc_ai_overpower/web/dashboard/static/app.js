document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const errorMessage = document.getElementById('error-message');
    const logoutButton = document.getElementById('logout-button');
    const navLinks = document.querySelectorAll('.nav-link');
    const dashboardPages = document.querySelectorAll('.dashboard-page');

    const API_BASE_URL = window.location.origin; // MCP server runs on the same origin as the web server

    // --- Navigation Logic ---
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('data-target');

            navLinks.forEach(nav => nav.classList.remove('active'));
            link.classList.add('active');

            dashboardPages.forEach(page => page.style.display = 'none');
            document.getElementById(targetId).style.display = 'block';
        });
    });

    // --- Authentication Logic ---
    function getToken() {
        return localStorage.getItem('skynet_jwt_token');
    }

    function setToken(token) {
        localStorage.setItem('skynet_jwt_token', token);
    }

    function removeToken() {
        localStorage.removeItem('skynet_jwt_token');
    }

    async function checkLogin() {
        const token = getToken();
        if (!token) {
            // Not logged in, redirect to login if not already there
            if (window.location.pathname !== '/') {
                window.location.href = '/';
            }
        } else {
            // Logged in, redirect to dashboard if not already there
            if (window.location.pathname !== '/dashboard') {
                window.location.href = '/dashboard';
            }
            // Load dashboard data
            await loadDashboardData();
        }
    }

    async function handleLogin(event) {
        event.preventDefault();
        errorMessage.textContent = '';

        const username = loginForm.username.value;
        const password = loginForm.password.value;

        try {
            const response = await fetch(`${API_BASE_URL}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Login failed');
            }

            const data = await response.json();
            setToken(data.access_token);
            window.location.href = '/dashboard';
        } catch (error) {
            errorMessage.textContent = error.message;
            console.error('Login error:', error);
        }
    }

    function handleLogout() {
        removeToken();
        window.location.href = '/';
    }

    // --- Dashboard Data Loading ---
    async function fetchData(endpoint) {
        const token = getToken();
        if (!token) {
            handleLogout(); // Redirect to login if token is missing
            return;
        }
        try {
            const response = await fetch(`${API_BASE_URL}/tool/${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({}), // MCP tool calls generally expect an empty JSON body if no args
            });

            if (response.status === 401) {
                handleLogout(); // Token expired or invalid
                return;
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Failed to fetch ${endpoint}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`Error fetching ${endpoint}:`, error);
            return null;
        }
    }

    async function loadDashboardData() {
        // Fetch Total Campaigns and Total Content (Placeholder for now)
        // These would come from specific MCP tools later
        document.getElementById('total-campaigns').textContent = '...'; // Replace with actual data later
        document.getElementById('total-content').textContent = '...'; // Replace with actual data later

        // Example for listing campaigns (requires an MCP tool 'list_campaigns' to be implemented)
        // const campaigns = await fetchData('list_campaigns');
        // if (campaigns) {
        //     const campaignsTableBody = document.getElementById('campaigns-table-body');
        //     campaignsTableBody.innerHTML = '';
        //     if (campaigns.length === 0) {
        //         campaignsTableBody.innerHTML = '<tr><td colspan="5">No campaigns found.</td></tr>';
        //     } else {
        //         campaigns.forEach(campaign => {
        //             const row = campaignsTableBody.insertRow();
        //             row.innerHTML = `
        //                 <td>${campaign.id}</td>
        //                 <td>${campaign.product}</td>
        //                 <td>${campaign.status}</td>
        //                 <td>${campaign.content_count}</td>
        //                 <td>${new Date(campaign.created_at).toLocaleString()}</td>
        //             `;
        //         });
        //     }
        // }

        // Example for listing content (requires an MCP tool 'list_content' to be implemented)
        // const content = await fetchData('list_content');
        // if (content) {
        //     const contentTableBody = document.getElementById('content-table-body');
        //     contentTableBody.innerHTML = '';
        //     if (content.length === 0) {
        //         contentTableBody.innerHTML = '<tr><td colspan="6">No content found.</td></tr>';
        //     } else {
        //         content.forEach(item => {
        //             const row = contentTableBody.insertRow();
        //             row.innerHTML = `
        //                 <td>${item.id}</td>
        //                 <td>${item.campaign_id}</td>
        //                 <td>${item.platform}</td>
        //                 <td>${item.status}</td>
        //                 <td><a href="${item.url}" target="_blank">Link</a></td>
        //                 <td>${new Date(item.created_at).toLocaleString()}</td>
        //             `;
        //         });
        //     }
        // }
    }

    // --- Initialize ---
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    if (logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }

    checkLogin();
});
