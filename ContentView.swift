import SwiftUI
import WebKit
import Network

struct ContentView: View {
    @State private var isLoading = true
    @State private var loadingProgress: Double = 0.0
    @State private var hasLoadedOnce = false
    @State private var isOnline = true
    @State private var loadingMessage = "読み込み中"
    @State private var showRetryButton = false
    
    private let networkMonitor = NWPathMonitor()
    private let networkQueue = DispatchQueue(label: "NetworkMonitor")
    
    var body: some View {
        ZStack {
            // ステータスバー領域の背景
            Color(.systemBackground)
                .ignoresSafeArea(.container, edges: .top)
            
            // WebViewコンテンツ
            WebViewContainer(isLoading: $isLoading, loadingProgress: $loadingProgress, hasLoadedOnce: $hasLoadedOnce)
                .ignoresSafeArea(.container, edges: [.bottom, .leading, .trailing])
                .opacity(hasLoadedOnce ? 1 : 0)
                .animation(.easeInOut(duration: 0.5), value: hasLoadedOnce)
            
            // ローディング画面（WebView読み込み完了まで表示）
            if !hasLoadedOnce {
                LoadingView(
                    progress: loadingProgress,
                    isOnline: isOnline,
                    message: loadingMessage,
                    showRetryButton: showRetryButton,
                    onRetry: retryConnection
                )
                .transition(.opacity)
                .animation(.easeInOut(duration: 0.3), value: hasLoadedOnce)
                .zIndex(1) // WebViewより前面に表示
            }
        }
        .onAppear {
            // アプリ起動時の初期設定
            isLoading = true
            loadingProgress = 0.0
            loadingMessage = "読み込み中"
            showRetryButton = false
            startNetworkMonitoring()
        }
        .onDisappear {
            stopNetworkMonitoring()
        }
    }
    
    private func startNetworkMonitoring() {
        networkMonitor.pathUpdateHandler = { path in
            DispatchQueue.main.async {
                self.isOnline = path.status == .satisfied
                
                // オフライン状態の処理（初回読み込み時のみ）
                if !self.hasLoadedOnce {
                    if !self.isOnline {
                        self.loadingMessage = "オフラインです"
                        self.showRetryButton = true
                        self.isLoading = true
                    } else {
                        self.loadingMessage = "読み込み中"
                        self.showRetryButton = false
                        self.isLoading = true
                    }
                }
            }
        }
        networkMonitor.start(queue: networkQueue)
    }
    
    private func stopNetworkMonitoring() {
        networkMonitor.cancel()
    }
    
    private func retryConnection() {
        if isOnline && !hasLoadedOnce {
            loadingMessage = "再接続中"
            showRetryButton = false
            loadingProgress = 0.0
            isLoading = true
            
            // WebViewに再読み込みを通知
            NotificationCenter.default.post(name: .retryConnection, object: nil)
        }
    }
}

struct LoadingView: View {
    let progress: Double
    let isOnline: Bool
    let message: String
    let showRetryButton: Bool
    let onRetry: () -> Void
    
    @State private var animationOffset: CGFloat = 0
    @State private var pulseScale: CGFloat = 1.0
    
    var body: some View {
        ZStack {
            // 背景グラデーション
            LinearGradient(
                gradient: Gradient(colors: [
                    Color(red: 0.4, green: 0.8, blue: 1.0),
                    Color(red: 0.2, green: 0.6, blue: 0.9)
                ]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 40) {
                Spacer()
                
                // アプリアイコン風のデザイン
                ZStack {
                    // 外側の円
                    Circle()
                        .fill(Color.white.opacity(0.2))
                        .frame(width: 120, height: 120)
                        .scaleEffect(pulseScale)
                        .animation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true), value: pulseScale)
                    
                    // 内側のアイコン
                    ZStack {
                        RoundedRectangle(cornerRadius: 20)
                            .fill(Color.white)
                            .frame(width: 80, height: 80)
                            .shadow(color: .black.opacity(0.1), radius: 10, x: 0, y: 5)
                        
                        // 家のアイコン
                        VStack(spacing: 2) {
                            Image(systemName: "house.fill")
                                .font(.system(size: 24, weight: .medium))
                                .foregroundColor(Color(red: 0.2, green: 0.6, blue: 0.9))
                            
                            // グラフアイコン
                            Image(systemName: "chart.line.uptrend.xyaxis")
                                .font(.system(size: 16, weight: .medium))
                                .foregroundColor(Color(red: 0.4, green: 0.8, blue: 1.0))
                        }
                    }
                }
                .onAppear {
                    pulseScale = 1.1
                }
                
                // アプリ名
                VStack(spacing: 8) {
                    Text("LifePlan")
                        .font(.system(size: 32, weight: .bold, design: .rounded))
                        .foregroundColor(.white)
                    
                    Text("人生設計アプリ")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(.white.opacity(0.8))
                }
                
                Spacer()
                
                // プログレスバー
                VStack(spacing: 16) {
                    // プログレスバー
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 10)
                            .fill(Color.white.opacity(0.3))
                            .frame(height: 6)
                        
                        RoundedRectangle(cornerRadius: 10)
                            .fill(Color.white)
                            .frame(width: max(20, CGFloat(progress) * UIScreen.main.bounds.width * 0.6), height: 6)
                            .animation(.easeInOut(duration: 0.3), value: progress)
                    }
                    .frame(width: UIScreen.main.bounds.width * 0.6)
                    
                    // ローディングテキスト・ステータス表示
                    VStack(spacing: 12) {
                        HStack(spacing: 4) {
                            // ネットワーク状態アイコン
                            Image(systemName: isOnline ? "wifi" : "wifi.slash")
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(isOnline ? .white.opacity(0.8) : .red.opacity(0.8))
                            
                            Text(message)
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(.white.opacity(0.8))
                            
                            // アニメーションドット（オンライン時のみ）
                            if isOnline && !showRetryButton {
                                HStack(spacing: 2) {
                                    ForEach(0..<3) { index in
                                        Circle()
                                            .fill(Color.white.opacity(0.8))
                                            .frame(width: 4, height: 4)
                                            .offset(y: animationOffset)
                                            .animation(
                                                .easeInOut(duration: 0.6)
                                                .repeatForever()
                                                .delay(Double(index) * 0.2),
                                                value: animationOffset
                                            )
                                    }
                                }
                            }
                        }
                        
                        // 再試行ボタン
                        if showRetryButton {
                            Button(action: onRetry) {
                                HStack(spacing: 8) {
                                    Image(systemName: "arrow.clockwise")
                                        .font(.system(size: 14, weight: .medium))
                                    Text("再試行")
                                        .font(.system(size: 14, weight: .medium))
                                }
                                .foregroundColor(.white)
                                .padding(.horizontal, 20)
                                .padding(.vertical, 10)
                                .background(
                                    RoundedRectangle(cornerRadius: 20)
                                        .fill(Color.white.opacity(0.2))
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 20)
                                                .stroke(Color.white.opacity(0.3), lineWidth: 1)
                                        )
                                )
                            }
                            .disabled(!isOnline)
                            .opacity(isOnline ? 1.0 : 0.5)
                        }
                    }
                }
                
                Spacer()
                    .frame(height: 60)
            }
            .padding(.horizontal, 40)
        }
        .onAppear {
            animationOffset = -8
        }
    }
}

struct WebViewContainer: UIViewRepresentable {
    let url = URL(string: "https://139c7e8ce0f4.ngrok.app/")!
    @Binding var isLoading: Bool
    @Binding var loadingProgress: Double
    @Binding var hasLoadedOnce: Bool
    
    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        
        // JavaScript有効化
        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        configuration.defaultWebpagePreferences = preferences
        
        // ローカルストレージ許可
        configuration.websiteDataStore = WKWebsiteDataStore.default()
        
        // セキュリティ設定
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        configuration.allowsAirPlayForMediaPlayback = true
        configuration.allowsPictureInPictureMediaPlayback = true
        
        // パフォーマンス設定
        configuration.suppressesIncrementalRendering = false
        
        let webView = WKWebView(frame: .zero, configuration: configuration)
        
        // 背景設定（初回読み込み時は透明に）
        webView.isOpaque = false
        webView.backgroundColor = UIColor.clear
        webView.scrollView.backgroundColor = UIColor.clear
        
        // ステータスバー領域の背景色を確実に設定
        if let window = UIApplication.shared.windows.first {
            window.backgroundColor = UIColor.systemBackground
        }
        
        // スクロール設定
        webView.scrollView.bounces = true
        webView.scrollView.alwaysBounceVertical = false
        webView.scrollView.alwaysBounceHorizontal = false
        webView.scrollView.showsVerticalScrollIndicator = true
        webView.scrollView.showsHorizontalScrollIndicator = false
        
        // WebViewでの固定要素位置安定化
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.scrollView.scrollIndicatorInsets = UIEdgeInsets.zero
        
        // iOS特有の設定
        if #available(iOS 13.0, *) {
            webView.scrollView.automaticallyAdjustsScrollIndicatorInsets = false
        }
        
        // デリゲート設定
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        
        // プログレス監視の設定
        webView.addObserver(context.coordinator, forKeyPath: #keyPath(WKWebView.estimatedProgress), options: .new, context: nil)
        
        // より詳細なUser-Agent設定
        let deviceModel = UIDevice.current.model
        let systemVersion = UIDevice.current.systemVersion
        let scale = UIScreen.main.scale
        let screenSize = UIScreen.main.bounds.size
        
        webView.customUserAgent = "LifePlanApp/1.0 (iOS \(systemVersion); \(deviceModel); Scale/\(scale); Screen/\(Int(screenSize.width))x\(Int(screenSize.height)); WebView) AppleWebKit/605.1.15 (KHTML, like Gecko)"
        
        // 再接続通知の監視
        NotificationCenter.default.addObserver(
            context.coordinator,
            selector: #selector(context.coordinator.retryConnection),
            name: .retryConnection,
            object: nil
        )
        
        // キャッシュポリシー設定
        let request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalAndRemoteCacheData, timeoutInterval: 30.0)
        webView.load(request)
        
        return webView
    }
    
    func updateUIView(_ webView: WKWebView, context: Context) {
        // 初回のみロード（webView.urlがnilのときのみ）
        if webView.url == nil && !hasLoadedOnce {
            let request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalAndRemoteCacheData)
            webView.load(request)
        }
        // それ以外は何もしない
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        let parent: WebViewContainer
        private weak var webView: WKWebView?
        
        init(_ parent: WebViewContainer) {
            self.parent = parent
        }
        
        @objc func retryConnection() {
            guard let webView = self.webView else { return }
            let request = URLRequest(url: parent.url, cachePolicy: .reloadIgnoringLocalAndRemoteCacheData, timeoutInterval: 30.0)
            webView.load(request)
        }
        
        // プログレス監視
        override func observeValue(forKeyPath keyPath: String?, of object: Any?, change: [NSKeyValueChangeKey : Any]?, context: UnsafeMutableRawPointer?) {
            if keyPath == #keyPath(WKWebView.estimatedProgress) {
                if let webView = object as? WKWebView, !parent.hasLoadedOnce {
                    DispatchQueue.main.async {
                        // プログレスを滑らかに更新
                        let newProgress = webView.estimatedProgress
                        if newProgress > self.parent.loadingProgress {
                            self.parent.loadingProgress = newProgress
                        }
                    }
                }
            }
        }
        
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            print("ページ読み込み開始: \(webView.url?.absoluteString ?? "Unknown")")
            
            // WebViewの参照を保存
            self.webView = webView
            
            // 初回読み込み時のみローディング画面を表示
            if !parent.hasLoadedOnce {
                DispatchQueue.main.async {
                    self.parent.isLoading = true
                    self.parent.loadingProgress = 0.0
                }
            }
        }
        
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            print("ページ読み込み完了: \(webView.url?.absoluteString ?? "Unknown")")
            
            // 初回読み込み完了時のみローディング画面を非表示にする
            if !parent.hasLoadedOnce {
                // WebViewの背景を通常に戻す
                webView.isOpaque = true
                webView.backgroundColor = UIColor.systemBackground
                webView.scrollView.backgroundColor = UIColor.systemBackground
                
                // ローディング完了を少し遅延させてスムーズに見せる
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                    self.parent.isLoading = false
                    self.parent.loadingProgress = 1.0
                    self.parent.hasLoadedOnce = true
                }
            }
            
            // Safe Area情報を取得
            let safeAreaInsets = UIApplication.shared.windows.first?.safeAreaInsets ?? UIEdgeInsets.zero
            
            // ページ読み込み完了時にWebアプリに詳細情報を送信
            let deviceInfo = [
                "isNativeApp": true,
                "appVersion": "1.0",
                "platform": "iOS",
                "deviceModel": UIDevice.current.model,
                "systemVersion": UIDevice.current.systemVersion,
                "screenScale": UIScreen.main.scale,
                "screenSize": [
                    "width": UIScreen.main.bounds.width,
                    "height": UIScreen.main.bounds.height
                ],
                "safeAreaInsets": [
                    "top": safeAreaInsets.top,
                    "bottom": safeAreaInsets.bottom,
                    "left": safeAreaInsets.left,
                    "right": safeAreaInsets.right
                ],
                "timestamp": Date().timeIntervalSince1970
            ] as [String : Any]
            
            do {
                let jsonData = try JSONSerialization.data(withJSONObject: deviceInfo)
                let jsonString = String(data: jsonData, encoding: .utf8) ?? "{}"
                
                let script = """
                window.nativeAppInfo = \(jsonString);
                window.isNativeApp = true;
                window.appVersion = '1.0';
                
                // カスタムイベントを発火してWebアプリに通知
                if (typeof window.onNativeAppReady === 'function') {
                    window.onNativeAppReady(window.nativeAppInfo);
                }
                
                // DOM読み込み完了後にイベント発火
                if (document.readyState === 'complete') {
                    document.dispatchEvent(new CustomEvent('nativeAppReady', { detail: window.nativeAppInfo }));
                } else {
                    document.addEventListener('DOMContentLoaded', function() {
                        document.dispatchEvent(new CustomEvent('nativeAppReady', { detail: window.nativeAppInfo }));
                    });
                }
                
                console.log('Native app info injected:', window.nativeAppInfo);
                """
                
                webView.evaluateJavaScript(script) { result, error in
                    if let error = error {
                        print("JavaScript実行エラー: \(error)")
                    } else {
                        print("デバイス情報をWebアプリに送信完了")
                    }
                }
            } catch {
                print("JSON変換エラー: \(error)")
            }
        }
        
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("読み込みエラー: \(error.localizedDescription)")
            DispatchQueue.main.async {
                self.parent.isLoading = false
            }
            
            // ネットワークエラーの場合は再試行（初回読み込み時のみ）
            let nsError = error as NSError
            if nsError.domain == NSURLErrorDomain && [NSURLErrorNotConnectedToInternet, NSURLErrorTimedOut].contains(nsError.code) && !parent.hasLoadedOnce {
                DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                    print("ネットワークエラーのため3秒後に再試行")
                    DispatchQueue.main.async {
                        self.parent.isLoading = true
                        self.parent.loadingProgress = 0.0
                    }
                    let request = URLRequest(url: self.parent.url)
                    webView.load(request)
                }
            }
        }
        
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            print("初期読み込みエラー: \(error.localizedDescription)")
            DispatchQueue.main.async {
                self.parent.isLoading = false
            }
        }
        
        // メモリリーク防止のためのクリーンアップ
        deinit {
            NotificationCenter.default.removeObserver(self)
        }
        
        // ポップアップ対応
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if navigationAction.targetFrame == nil {
                webView.load(navigationAction.request)
            }
            return nil
        }
        
        // アラート対応
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            let alert = UIAlertController(title: "通知", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in
                completionHandler()
            })
            
            if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
               let window = windowScene.windows.first,
               let rootViewController = window.rootViewController {
                rootViewController.present(alert, animated: true)
            }
        }
        
        // 確認ダイアログ対応
        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            let alert = UIAlertController(title: "確認", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in
                completionHandler(true)
            })
            alert.addAction(UIAlertAction(title: "キャンセル", style: .cancel) { _ in
                completionHandler(false)
            })
            
            if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
               let window = windowScene.windows.first,
               let rootViewController = window.rootViewController {
                rootViewController.present(alert, animated: true)
            }
        }
        
        // プロンプト対応
        func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
            let alert = UIAlertController(title: "入力", message: prompt, preferredStyle: .alert)
            alert.addTextField { textField in
                textField.text = defaultText
            }
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in
                completionHandler(alert.textFields?.first?.text)
            })
            alert.addAction(UIAlertAction(title: "キャンセル", style: .cancel) { _ in
                completionHandler(nil)
            })
            
            if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
               let window = windowScene.windows.first,
               let rootViewController = window.rootViewController {
                rootViewController.present(alert, animated: true)
            }
        }
    }
}

// 通知名の拡張
extension Notification.Name {
    static let retryConnection = Notification.Name("retryConnection")
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
} 