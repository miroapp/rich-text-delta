import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    kotlin("jvm") version "2.4.10"
    kotlin("plugin.serialization") version "2.4.10"
    id("org.jlleitschuh.gradle.ktlint") version "14.2.0"
    `java-library`
    `maven-publish`
    signing
}

repositories {
    mavenCentral()
}

dependencies {
    api("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")
    implementation("org.bitbucket.cowwoc:diff-match-patch:1.2")

    testImplementation(platform("org.junit:junit-bom:5.14.0"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testImplementation("org.snakeyaml:snakeyaml-engine:2.9")
}

java {
    withSourcesJar()
    // Maven Central requires a javadoc jar; with no Java sources it is empty
    withJavadocJar()
}

tasks.withType<JavaCompile>().configureEach {
    options.release = 17
}

kotlin {
    explicitApi()
    compilerOptions {
        jvmTarget = JvmTarget.JVM_17
    }
}

publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
            pom {
                name = "rich-text-delta"
                description = "Kotlin/JVM implementation of Rich Text Delta, a fork of quill-delta with nested attribute maps"
                url = "https://github.com/miroapp/rich-text-delta"
                licenses {
                    license {
                        name = "BSD-3-Clause"
                        url = "https://opensource.org/license/bsd-3-clause"
                    }
                }
                developers {
                    developer {
                        name = "Miro"
                        organization = "Miro"
                        organizationUrl = "https://miro.com"
                    }
                }
                scm {
                    url = "https://github.com/miroapp/rich-text-delta"
                    connection = "scm:git:https://github.com/miroapp/rich-text-delta.git"
                    developerConnection = "scm:git:ssh://git@github.com/miroapp/rich-text-delta.git"
                }
            }
        }
    }
    repositories {
        // Central Portal's OSSRH-compatible staging endpoint. Uploads land in a staging
        // repository that must then be handed to the Portal; see publish-kotlin.yml.
        maven {
            name = "mavenCentral"
            url = uri("https://ossrh-staging-api.central.sonatype.com/service/local/staging/deploy/maven2/")
            credentials(PasswordCredentials::class)
        }
    }
}

signing {
    val signingKey = providers.gradleProperty("signingInMemoryKey")
    // unsigned when no key is configured, so publishToMavenLocal works without one
    if (signingKey.isPresent) {
        useInMemoryPgpKeys(signingKey.get(), providers.gradleProperty("signingInMemoryKeyPassword").orNull)
        sign(publishing.publications["maven"])
    }
}

ktlint {
    version = "1.8.0"
}

val corpusDir = layout.projectDirectory.dir("../../declarative-test-corpus")

tasks.test {
    useJUnitPlatform()
    inputs.dir(corpusDir).withPropertyName("corpus").withPathSensitivity(PathSensitivity.RELATIVE)
    systemProperty("corpus.root", corpusDir.asFile.absolutePath)
    testLogging {
        events("failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
