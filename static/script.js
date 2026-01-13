// Prepare chart data from courseData variable
function prepareChartData(data) {
    return {
        labels: data.map(item => item.course),
        datasets: [
            {
                label: 'Popularity (%)',
                data: data.map(item => item.popularity),
                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            },
            {
                label: 'Future Scope (%)',
                data: data.map(item => item.future_scope),
                backgroundColor: 'rgba(255, 99, 132, 0.7)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 1
            }
        ]
    };
}

function getChartOptions() {
    return {
        responsive: true,
        scales: {
            y: {
                beginAtZero: true,
                max: 100,
                ticks: {
                    stepSize: 10
                }
            }
        },
        plugins: {
            legend: {
                position: 'top'
            },
            title: {
                display: true,
                text: 'Career Graph: Course Popularity vs Future Scope'
            }
        }
    };
}

// Create the chart
function createCareerChart() {
    const ctx = document.getElementById('careerChart').getContext('2d');
    const data = prepareChartData(courseData);
    const options = getChartOptions();

    new Chart(ctx, {
        type: 'bar',
        data: data,
        options: options
    });
}

// Initialize the chart once the DOM is fully loaded
window.onload = function() {
    createCareerChart();
};
