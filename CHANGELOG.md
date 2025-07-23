# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.9.1] - 2024-01-23

### Added
- ✨ **Periodic URL Checking**: Automated background tests with configurable CHECK_INTERVAL
- ✨ **Ingress Class Support**: Display Ingress Class and Gateway information in UI
- ✨ **Responsive Design**: Comprehensive mobile, tablet, and desktop optimization
- ✨ **Enhanced Search**: Search now includes ingress class, gateway, and details fields
- ✨ **Memory Monitoring**: New `/memory` endpoint for tracking memory usage
- ✨ **Automated Release Workflow**: Semantic versioning based on commit messages
- ✨ **Multi-arch Builds**: Support for AMD64 and ARM64 architectures
- 📝 **Test Resources**: Added k8s-test/ directory with sample Kubernetes resources

### Changed
- 🎨 **UI Improvements**: 
  - Modern annotation buttons with count display
  - Better status badges with improved contrast
  - Optimized column widths and text overflow handling
  - Added horizontal scroll indicator for mobile tables
- 🚀 **Performance Optimizations**:
  - Removed emoji icons from logs to reduce processing overhead
  - Optimized log serialization for production environments
  - Improved cache management and TTL settings
  - Better resource utilization with configurable intervals
- 🔧 **Configuration Updates**:
  - Smart log format selection based on FLASK_ENV
  - Updated default CHECK_INTERVAL from 30s to 300s
  - Increased CACHE_TTL_SECONDS from 300s to 900s
  - Reduced MAX_CONCURRENT_REQUESTS from 5 to 3

### Fixed
- 🐛 **Helm Chart Fixes**:
  - Fixed ServiceAccount reference in ClusterRoleBinding
  - Standardized ConfigMap naming to portal-checker-config
  - Fixed probe configurations for better stability
- 🐛 **Dependency Conflicts**:
  - Resolved aiosignal version conflict
  - Updated aiohttp to compatible version
- 🐛 **Development Mode**: Skip file writing in dev mode to avoid read-only filesystem errors

### Security
- 🔒 Updated dependencies to latest secure versions
- 🔒 Improved RBAC configuration for least privilege access

## [2.9.0] - 2024-01-20

### Added
- Initial support for HTTPRoute resources
- Basic Kubernetes resource discovery
- Web dashboard with sorting and filtering
- URL exclusion patterns

## [2.8.1] - 2024-01-15

### Added
- Initial release with Ingress monitoring
- Basic health check functionality
- Simple web interface

---

## Version History

- **2.9.x**: Performance improvements and responsive design
- **2.8.x**: HTTPRoute support and enhanced monitoring
- **2.7.x**: Initial stable release with core features