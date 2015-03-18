module.exports = function(grunt) {
  grunt.loadNpmTasks('grunt-contrib-concat');
  grunt.loadNpmTasks('grunt-contrib-uglify');

  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),
    concat: {
      js: {
        src: ['src/jquery-2.1.3.js', 'src/chess.js', 'src/chessboard-0.3.0.js', 'src/client.js'],
        dest: 'static/client.js'
      }
    },
    uglify: {
      options: {
        compress: true,
        mangle: true,
        sourceMap: true
      },
      build: {
        src: 'static/client.js',
        dest: 'static/client.min.js'
      }
    }
  });

  grunt.registerTask('default', ['concat', 'uglify']);
};
