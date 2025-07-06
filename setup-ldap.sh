#!/bin/bash

echo "🚀 Setting up LDAP test environment..."

# Stop and clean any existing containers
echo "🧹 Cleaning up existing containers..."
docker-compose -f docker-compose-meli-challenge.yml down -v 2>/dev/null

# Start the LDAP stack
echo "🐳 Starting LDAP containers..."
docker-compose -f docker-compose-meli-challenge.yml up -d

# Wait for LDAP to be ready
echo "⏳ Waiting for LDAP server to be ready..."
sleep 15

# Test connection
echo "🔍 Testing LDAP connection..."
for i in {1..10}; do
    if ldapsearch -x -H ldap://localhost:389 -D "cn=admin,dc=meli,dc=com" -w itachi -b "dc=meli,dc=com" -s base > /dev/null 2>&1; then
        echo "✅ LDAP server is ready!"
        break
    else
        echo "⏳ Waiting for LDAP... (attempt $i/10)"
        sleep 3
    fi
    
    if [ $i -eq 10 ]; then
        echo "❌ LDAP server failed to start properly"
        exit 1
    fi
done

# Load LDIF files
echo "📂 Loading LDAP data..."

echo "   - Loading organizational structure..."
ldapadd -x -H ldap://localhost:389 -D "cn=admin,dc=meli,dc=com" -w itachi -f users_groups/01-structure.ldif

echo "   - Loading users..."
ldapadd -x -H ldap://localhost:389 -D "cn=admin,dc=meli,dc=com" -w itachi -f users_groups/02-users.ldif

echo "   - Loading groups..."
ldapadd -x -H ldap://localhost:389 -D "cn=admin,dc=meli,dc=com" -w itachi -f users_groups/03-groups.ldif

# Verify setup
echo "🔍 Verifying setup..."
echo "   - Users found: $(ldapsearch -x -H ldap://localhost:389 -D "cn=admin,dc=meli,dc=com" -w itachi -b "ou=users,dc=meli,dc=com" "(objectClass=inetOrgPerson)" cn | grep -c "^cn:")"
echo "   - Groups found: $(ldapsearch -x -H ldap://localhost:389 -D "cn=admin,dc=meli,dc=com" -w itachi -b "ou=groups,dc=meli,dc=com" "(objectClass=groupOfNames)" cn | grep -c "^cn:")"

echo ""
echo "🎉 LDAP setup complete!"
echo ""
echo "📋 Connection details:"
echo "   Server: ldap://localhost:389"
echo "   Admin DN: CN=admin,DC=meli,DC=com"
echo "   Password: itachi"
echo "   Base DN: DC=meli,DC=com"
echo ""
echo "🌐 phpLDAPAdmin: http://localhost:8080"
echo ""
echo "🤖 To see the server logs: docker logs -f ldap-meli-challenge-server" 