const ctx = document.getElementById('incomeExpenseChart');

new Chart(ctx, {
    type: 'bar',

    data: {
        labels: ['Income', 'Expense'],

        datasets: [{
            label: 'Amount (₹)',
            data: [
                totalIncomeValue, totalExpenseValue
            ],
    backgroundColor: [
        '#4CAF50',
        '#F44336'
    ],
    borderWidth: 1,
    barThickness: 35
}]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,

            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });