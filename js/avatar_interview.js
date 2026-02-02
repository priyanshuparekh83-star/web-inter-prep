document.addEventListener('DOMContentLoaded', function () {
    // State variables
    let currentQuestions = [];
    let currentQuestionIndex = 0;
    let interviewId = null;
    let answers = [];
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let stream = null;
    let interviewData = null;

    // DOM Elements
    const setupForm = document.getElementById('setupForm');
    const interviewSetup = document.getElementById('interviewSetup');
    const interviewContent = document.getElementById('interviewContent');
    const completionScreen = document.getElementById('completionScreen');

    // Interview Elements
    const avatarPlayer = document.getElementById('avatarPlayer');
    const currentQuestionEl = document.getElementById('currentQuestion');
    const userVideo = document.getElementById('userVideo');
    const micButton = document.getElementById('micButton');
    const micStatus = document.getElementById('micStatus');
    const nextButton = document.getElementById('nextButton');
    const transcriptText = document.getElementById('transcriptText');
    const progressText = document.getElementById('progressText');
    const progressFill = document.getElementById('progressFill');
    const progressSection = document.querySelector('.progress-section');
    const recordingIndicator = document.getElementById('recordingIndicator');
    const videoOverlay = document.getElementById('videoOverlay');

    // Completion Elements
    const overallScoreSection = document.getElementById('overallScoreSection');
    const overallScoreEl = document.getElementById('overallScore');
    const detailedFeedbackSection = document.getElementById('detailedFeedbackSection');
    const submitButton = document.getElementById('submitButton');
    const viewHistoryButton = document.getElementById('viewHistoryButton');
    const restartButton = document.getElementById('restartButton');

    // Event Listeners
    if (setupForm) {
        setupForm.addEventListener('submit', handleSetupSubmit);
    }

    if (micButton) {
        micButton.addEventListener('click', toggleRecording);
    }

    if (nextButton) {
        nextButton.addEventListener('click', handleNextQuestion);
    }

    if (submitButton) {
        submitButton.addEventListener('click', saveInterview);
    }

    if (restartButton) {
        restartButton.addEventListener('click', () => window.location.reload());
    }

    if (viewHistoryButton) {
        viewHistoryButton.addEventListener('click', () => {
            alert('View history feature coming soon!'); // Placeholder
        });
    }

    // Initialize Camera
    async function initCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            userVideo.srcObject = stream;
            videoOverlay.style.display = 'none';
            return true;
        } catch (err) {
            console.error("Camera access denied:", err);
            showToast("Camera access is required for the interview.", "error");
            return false;
        }
    }

    // Handle Setup Form Submission
    async function handleSetupSubmit(e) {
        e.preventDefault();

        const jobRole = document.getElementById('jobRole').value;
        const company = document.getElementById('targetCompany').value;
        const experience = document.getElementById('experienceLevel').value;
        const count = document.getElementById('questionCount').value;

        const submitBtn = setupForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Generating...';

        try {
            // Save setup data
            interviewData = {
                jobRole,
                company,
                experienceLevel: experience
            };

            // Request questions from API
            const response = await fetch('/api/generate_question', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    role: jobRole,
                    company: company,
                    difficulty: experience,
                    question_count: parseInt(count),
                    generate_multiple: true
                })
            });

            const data = await response.json();


            if (data.questions && data.questions.length > 0) {
                currentQuestions = data.questions;
                startInterview();
            } else if (data.question) {
                currentQuestions = [data.question];
                startInterview();
            } else {
                showToast("Failed to generate questions. Please try again.", "error");
            }

        } catch (error) {
            console.error("Error generating questions:", error);
            showToast("An error occurred. Please try again.", "error");
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    }

    // Start Interview Session
    async function startInterview() {
        const hasCamera = await initCamera();
        if (!hasCamera) return;

        interviewSetup.style.display = 'none';
        interviewContent.style.display = 'grid';
        progressSection.style.display = 'block';

        currentQuestionIndex = 0;
        answers = [];

        loadQuestion(0);
    }

    // Load Question
    function loadQuestion(index) {
        const question = currentQuestions[index];
        currentQuestionEl.textContent = question;

        // Update Progress
        progressText.textContent = `Question ${index + 1} of ${currentQuestions.length}`;
        const progressPercent = ((index) / currentQuestions.length) * 100;
        progressFill.style.width = `${progressPercent}%`;

        // Reset UI for new question
        transcriptText.textContent = "Click the microphone to start answering based on the question above.";
        transcriptText.style.fontStyle = 'italic';
        transcriptText.style.color = '#6c757d';
        nextButton.style.display = 'none';
        micButton.disabled = false;
        micButton.classList.remove('recording');
        micStatus.textContent = "Click microphone when ready to answer";

        // Play Avatar Video (Simulated/Demo)
        playAvatarIntro();
    }

    async function playAvatarIntro() {
        // In a real implementation with D-ID, we would generate a specific video here.
        // For now, we simulate the avatar "speaking" by playing the looping video
        // and showing a speaking indicator or subtitle.

        avatarPlayer.play().catch(e => console.log("Auto-play prevented"));

        // Simulate reading the question
        micButton.disabled = true;
        micStatus.textContent = "Interviewer is speaking...";

        // Estimate reading time based on word count (avg 150 wpm)
        const wordCount = currentQuestionEl.textContent.split(' ').length;
        const readingTime = Math.max(2000, (wordCount / 150) * 60 * 1000);

        setTimeout(() => {
            micButton.disabled = false;
            micStatus.textContent = "Click microphone to start answering";
        }, readingTime);
    }

    // Toggle Recording
    async function toggleRecording() {
        if (!isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    }

    function startRecording() {
        if (!stream) return;

        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = processRecording;

        mediaRecorder.start();
        isRecording = true;

        micButton.classList.add('recording');
        micButton.innerHTML = '<i class="fas fa-stop"></i>';
        micStatus.textContent = "Recording... Click to stop";
        recordingIndicator.style.display = 'flex';
        transcriptText.textContent = "Listening...";
        transcriptText.style.fontStyle = 'normal';
        transcriptText.style.color = '#2c3e50';
    }

    function stopRecording() {
        mediaRecorder.stop();
        isRecording = false;

        micButton.classList.remove('recording');
        micButton.classList.add('processing'); // Add a processing class if needed
        micButton.innerHTML = '<i class="fas fa-microphone"></i>';
        micButton.disabled = true; // Disable until processing is done
        micStatus.textContent = "Processing answer...";
        recordingIndicator.style.display = 'none';
        transcriptText.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Transcribing...';
    }

    async function processRecording() {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('file', audioBlob, 'answer.wav');

        try {
            const response = await fetch('/transcribe_audio', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.status === 'success') {
                const transcript = data.transcription;
                transcriptText.textContent = transcript;

                // Store answer
                answers.push({
                    question: currentQuestions[currentQuestionIndex],
                    answer: transcript
                });

                // Show Next Button
                micButton.style.display = 'none'; // Hide mic button
                micStatus.textContent = "Answer recorded";
                nextButton.style.display = 'inline-block';

            } else {
                const errorMsg = data.details || data.error || "Error transcribing audio. Please try again.";
                transcriptText.textContent = `Error: ${errorMsg}`;
                micButton.disabled = false;
                micStatus.textContent = "Try again";
            }

        } catch (error) {
            console.error("Transcription error:", error);
            transcriptText.textContent = "Network error. Please try again.";
            micButton.disabled = false;
        }
    }

    // Handle Next Question
    function handleNextQuestion() {
        // Restore mic button
        micButton.style.display = 'flex';

        if (currentQuestionIndex < currentQuestions.length - 1) {
            currentQuestionIndex++;
            loadQuestion(currentQuestionIndex);
        } else {
            finishInterview();
        }
    }

    // Finish Interview
    async function finishInterview() {
        interviewContent.style.display = 'none';
        progressSection.style.display = 'none';
        completionScreen.style.display = 'block';

        // Stop camera
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }

        // Evaluate all answers
        await evaluateSession();
    }

    async function evaluateSession() {
        // Calculate a mock score for now until we implement the bulk evaluation API
        // In a real app, we would send all answers to the backend for comprehensive analysis

        let totalScore = 0;
        let evaluatedCount = 0;

        // Show loading state for results
        overallScoreEl.innerHTML = '<i class="fas fa-spinner fa-spin" style="font-size: 1.5rem"></i>';

        // We'll evaluate the last answer to get a sample feedback
        if (answers.length > 0) {
            const lastAnswer = answers[answers.length - 1];

            try {
                const response = await fetch('/api/evaluate_answer_detailed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: lastAnswer.question,
                        transcript: lastAnswer.answer,
                        video_duration: 30 // Mock duration
                    })
                });

                const data = await response.json();

                if (data) {
                    // Update UI with results
                    overallScoreSection.style.display = 'flex';
                    detailedFeedbackSection.style.display = 'block';
                    document.getElementById('summarySection').style.display = 'grid';

                    overallScoreEl.textContent = data.overall_score || 8.5;

                    // Update category scores
                    if (data.transcript_analysis) {
                        updateCategoryScore('content', data.transcript_analysis.content_quality);
                        updateCategoryScore('communication', data.transcript_analysis.communication);
                        updateCategoryScore('engagement', data.transcript_analysis.engagement); // Use engagement as posture proxy or similar
                    }

                    // Update lists
                    updateList('strengthsList', data.improvement_tips ? ['Good articulation', 'Relevance to topic'] : []);
                    updateList('improvementsList', data.improvement_tips || []);

                }
            } catch (error) {
                console.error("Evaluation error:", error);
                overallScoreEl.textContent = "N/A";
            }
        }
    }

    function updateCategoryScore(idPrefix, data) {
        if (!data) return;
        document.getElementById(`${idPrefix}Score`).textContent = `${data.score}/10`;
        document.getElementById(`${idPrefix}Feedback`).textContent = data.feedback;
        document.getElementById(`${idPrefix}Suggestions`).textContent = `• ${data.suggestions}`;
    }

    function updateList(elementId, items) {
        const list = document.getElementById(elementId);
        if (!list || !items) return;

        list.innerHTML = items.map(item => `<li>${item}</li>`).join('');
    }

    async function saveInterview() {
        const btn = submitButton;
        const originalContent = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="submission-loader"></span>Saving...';

        try {
            const response = await fetch('/api/avatar_interview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jobRole: interviewData.jobRole,
                    company: interviewData.company,
                    experienceLevel: interviewData.experienceLevel,
                    answers: answers,
                    completed: true,
                    videoRecorded: true
                })
            });

            const data = await response.json();
            if (data.status === 'saved') {
                showToast("Interview saved successfully!", "success");
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1500);
            } else {
                showToast("Failed to save interview.", "error");
            }
        } catch (error) {
            console.error("Save error:", error);
            showToast("Network error while saving.", "error");
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalContent;
        }
    }

    function showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        const content = toast.querySelector('.toast-message');
        const icon = toast.querySelector('.toast-icon');

        content.textContent = message;
        toast.className = `toast show ${type}`;

        if (type === 'error') {
            icon.className = 'toast-icon fas fa-exclamation-circle text-danger';
        } else if (type === 'success') {
            icon.className = 'toast-icon fas fa-check-circle text-success';
        } else {
            icon.className = 'toast-icon fas fa-info-circle';
        }

        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
});
