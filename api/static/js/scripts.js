// api/static/js/scripts.js

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('url-form');
    const statusDiv = document.getElementById('status');

    if (form) {  // Check if the form exists on the page
        form.addEventListener('submit', function(e) {
            e.preventDefault(); // Prevent the default form submission

            const urlInput = document.getElementById('url').value;
            statusDiv.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                Fetching information...
            `;
            statusDiv.classList.remove('text-success', 'text-danger');
            statusDiv.classList.add('text-primary');

            fetch('/scrape', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: urlInput })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    statusDiv.innerHTML = `<span class="text-success">${data.message}</span>`;
                    // Optionally, redirect to the products page after a short delay
                    setTimeout(() => {
                        window.location.href = '/products';
                    }, 1500);
                } else {
                    statusDiv.innerHTML = `<span class="text-danger">${data.message}</span>`;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                statusDiv.innerHTML = `<span class="text-danger">An error occurred while adding the product.</span>`;
            });
        });
    }
});